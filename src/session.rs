//! One authenticated helper, reachable only through the creating process's pipes.
use crate::system::{self, R};
use std::io::{Read, Write};
const MAX_ARGS: u32 = 3;
const MAX_ARG: usize = 4096;
const MAX_REPLY: usize = 4 * 1024 * 1024;
unsafe extern "C" {
    fn prctl(option: i32, ...) -> i32;
    fn getppid() -> u32;
}
fn number(input: &mut impl Read, clean_eof: bool) -> R<Option<u32>> {
    let mut bytes = [0u8; 4];
    match input.read(&mut bytes[..1]).map_err(|e| e.to_string())? {
        0 if clean_eof => return Ok(None),
        0 => return Err("Truncated session frame".into()),
        _ => (),
    }
    input
        .read_exact(&mut bytes[1..])
        .map_err(|e| e.to_string())?;
    Ok(Some(u32::from_be_bytes(bytes)))
}
fn serve_io(
    input: &mut impl Read,
    output: &mut impl Write,
    mut dispatch: impl FnMut(&[String]) -> R<String>,
) -> R<String> {
    loop {
        let Some(count) = number(input, true)? else {
            return Ok(String::new());
        };
        if count == 0 {
            return Ok(String::new());
        }
        if count > MAX_ARGS {
            return Err("Too many session arguments".into());
        }
        let mut args = Vec::new();
        for _ in 0..count {
            let length = number(input, false)?.unwrap() as usize;
            if length > MAX_ARG {
                return Err("Session argument too large".into());
            }
            let mut value = vec![0u8; length];
            input.read_exact(&mut value).map_err(|e| e.to_string())?;
            args.push(String::from_utf8(value).map_err(|_| "Invalid session UTF-8")?);
        }
        let result = dispatch(&args);
        let (mut status, mut text) = match result {
            Ok(text) => (0u8, text),
            Err(error) => (1u8, error),
        };
        if text.len() > MAX_REPLY {
            status = 1;
            text = "Session response too large / 响应过大".into();
        }
        output
            .write_all(&[status])
            .and_then(|_| output.write_all(&(text.len() as u32).to_be_bytes()))
            .and_then(|_| output.write_all(text.as_bytes()))
            .and_then(|_| output.flush())
            .map_err(|e| e.to_string())?;
    }
}
pub fn serve(dispatch: impl FnMut(&[String]) -> R<String>) -> R<String> {
    if !system::root() {
        return Err("Session helper requires polkit authorization".into());
    }
    // A dead GUI cannot leave an authorized helper behind, even if a pipe leaked.
    let parent = unsafe { getppid() };
    if parent <= 1 || unsafe { prctl(1, 15i32) } != 0 || unsafe { getppid() } != parent {
        return Err("Cannot bind helper lifetime to its parent".into());
    }
    serve_io(
        &mut std::io::stdin().lock(),
        &mut std::io::stdout().lock(),
        dispatch,
    )
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    fn frame(args: &[&str]) -> Vec<u8> {
        let mut b = (args.len() as u32).to_be_bytes().to_vec();
        for a in args {
            b.extend((a.len() as u32).to_be_bytes());
            b.extend(a.as_bytes());
        }
        b
    }
    #[test]
    fn reuses_connection_and_closes() {
        let mut bytes = frame(&["list"]);
        bytes.extend(frame(&["bad"]));
        bytes.extend(frame(&[]));
        let mut out = Vec::new();
        let mut calls = 0;
        serve_io(&mut Cursor::new(bytes), &mut out, |a| {
            calls += 1;
            if a[0] == "list" {
                Ok("ok".into())
            } else {
                Err("denied".into())
            }
        })
        .unwrap();
        assert_eq!(calls, 2);
        assert_eq!(
            out,
            [
                vec![0, 0, 0, 0, 2],
                b"ok".to_vec(),
                vec![1, 0, 0, 0, 6],
                b"denied".to_vec()
            ]
            .concat()
        );
    }
    #[test]
    fn malformed_frames_never_dispatch() {
        let cases = vec![
            4u32.to_be_bytes().to_vec(),
            [1u32.to_be_bytes(), 4097u32.to_be_bytes()].concat(),
            vec![0, 0, 0],
            vec![0, 0, 0, 1, 0, 0, 0, 1, 255],
        ];
        for b in cases {
            let mut called = false;
            assert!(serve_io(&mut Cursor::new(b), &mut Vec::new(), |_| {
                called = true;
                Ok(String::new())
            })
            .is_err());
            assert!(!called);
        }
    }
    #[test]
    fn clean_eof_is_shutdown() {
        assert!(serve_io(&mut Cursor::new(Vec::new()), &mut Vec::new(), |_| panic!()).is_ok());
    }
    #[test]
    fn oversized_reply_is_bounded() {
        let mut out = Vec::new();
        serve_io(&mut Cursor::new(frame(&["logs"])), &mut out, |_| {
            Ok("x".repeat(MAX_REPLY + 1))
        })
        .unwrap();
        assert_eq!(out[0], 1);
        assert!(out.len() < 256);
    }
}
