//! Conservative static GRUB menu reader. No shell code is ever evaluated.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub selector: String,
    pub title: String,
}

// Tokenize quotes, escapes, comments and braces; reject unterminated input.
fn tokens(input: &str) -> Result<Vec<String>, String> {
    let mut out = Vec::new();
    let mut word = String::new();
    let mut quote = None;
    let mut escape = false;
    let mut comment = false;
    let mut expansion = 0;
    for c in input.chars() {
        if comment {
            if c == '\n' {
                comment = false;
                out.push("\n".into());
            }
            continue;
        }
        if escape {
            if c != '\n' {
                word.push(c);
            }
            escape = false;
            continue;
        }
        if c == '\\' && quote != Some('\'') {
            escape = true;
            continue;
        }
        if let Some(q) = quote {
            if c == q {
                quote = None;
            } else {
                word.push(c);
            }
            continue;
        }
        if expansion > 0 {
            word.push(c);
            if c == '{' {
                expansion += 1;
            }
            if c == '}' {
                expansion -= 1;
            }
            continue;
        }
        if c == '{' && word.ends_with('$') {
            word.push(c);
            expansion = 1;
            continue;
        }
        match c {
            '\'' | '"' => quote = Some(c),
            '#' if word.is_empty() => comment = true,
            '{' | '}' | ';' | '\n' => {
                if !word.is_empty() {
                    out.push(std::mem::take(&mut word));
                }
                out.push(if c == '{' || c == '}' {
                    format!("\x01{c}")
                } else {
                    c.to_string()
                });
            }
            c if c.is_whitespace() => {
                if !word.is_empty() {
                    out.push(std::mem::take(&mut word));
                }
            }
            _ => word.push(c),
        }
    }
    if quote.is_some() || escape || expansion > 0 {
        return Err("Unterminated GRUB quote or escape / GRUB 引号未闭合".into());
    }
    if !word.is_empty() {
        out.push(word);
    }
    Ok(out)
}

pub fn parse(input: &str) -> Result<Vec<Entry>, String> {
    let ts = tokens(input)?;
    let mut out = Vec::new();
    let mut stack: Vec<u8> = Vec::new();
    let mut counts = vec![0usize];
    let mut path: Vec<String> = Vec::new();
    let mut titles: Vec<String> = Vec::new();
    let mut i = 0;
    while i < ts.len() {
        let boundary = i == 0 || ["\n", ";", "\x01{", "\x01}"].contains(&ts[i - 1].as_str());
        if boundary
            && stack.iter().all(|kind| *kind == 1)
            && (ts[i] == "menuentry" || ts[i] == "submenu")
        {
            let submenu = ts[i] == "submenu";
            let title = ts.get(i + 1).ok_or("Missing menu title")?.clone();
            let index = *counts.last().unwrap();
            *counts.last_mut().unwrap() += 1;
            i += 2;
            let mut id = None;
            while i < ts.len() && ts[i] != "\x01{" {
                if ts[i] == "\x01}" {
                    return Err("Malformed GRUB header".into());
                }
                if ts[i] == "--id"
                    || ts[i] == "$menuentry_id_option"
                    || ts[i] == "${menuentry_id_option}"
                {
                    i += 1;
                    id = ts.get(i).cloned();
                } else if let Some(v) = ts[i].strip_prefix("--id=") {
                    id = Some(v.to_owned());
                }
                i += 1;
            }
            if i == ts.len() {
                return Err("Missing GRUB opening brace".into());
            }
            // Numeric paths are valid even when IDs contain expansions or delimiters.
            let component = id
                .filter(|s| {
                    !s.is_empty()
                        && !s.contains(['$', '>', '\n', '\r'])
                        && !s.starts_with('-')
                        && !s.bytes().all(|b| b.is_ascii_digit())
                })
                .unwrap_or(index.to_string());
            if submenu {
                path.push(component);
                titles.push(title);
                counts.push(0);
                stack.push(1);
            } else {
                let mut p = path.clone();
                p.push(component);
                let mut t = titles.clone();
                t.push(title);
                out.push(Entry {
                    selector: p.join(">"),
                    title: t.join(" / "),
                });
                stack.push(2);
            }
        } else if ts[i] == "\x01{" {
            stack.push(0);
        } else if ts[i] == "\x01}" {
            let sub = stack.pop().ok_or("Unbalanced GRUB braces")?;
            if sub == 1 {
                path.pop();
                titles.pop();
                counts.pop();
            }
        }
        i += 1;
    }
    if !stack.is_empty() {
        return Err("Unbalanced GRUB braces".into());
    }
    if out.is_empty() {
        return Err("No static GRUB entries / 没有可识别的 GRUB 启动项".into());
    }
    let mut selectors = std::collections::HashSet::new();
    for e in &out {
        if !selectors.insert(&e.selector) {
            return Err("Ambiguous duplicate GRUB selectors".into());
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn nested() {
        let s = "# menuentry 'fake' {}\nmenuentry 'Debian' --id deb { echo 'a { b }'; }\nsubmenu 'Advanced' $menuentry_id_option adv { menuentry 'Recovery' --id rec { if true; then echo x; fi; } submenu 'More' { menuentry 'Old' { } } }\nmenuentry 'Windows' { }";
        let e = parse(s).unwrap();
        assert_eq!(
            e.iter().map(|e| e.selector.as_str()).collect::<Vec<_>>(),
            ["deb", "adv>rec", "adv>1>0", "2"]
        );
    }
    #[test]
    fn rejects_broken() {
        for s in ["menuentry 'oops {", "menuentry x {", "}", "#nothing"] {
            assert!(parse(s).is_err());
        }
    }
    #[test]
    fn quoted_titles() {
        assert_eq!(
            parse("menuentry \"Bill's OS\" --id=x {} ").unwrap()[0].title,
            "Bill's OS"
        );
    }
    #[test]
    fn real_fixture() {
        let e = parse(include_str!("../tests/fixtures/grub.cfg")).unwrap();
        assert_eq!(e.len(), 3);
        assert_eq!(e[1].selector, "gnulinux-advanced-123>recovery-123");
    }
    #[test]
    fn braces_and_expansions() {
        let e=parse("set x=${value}\nmenuentry 'OS' ${menuentry_id_option} 'os-id' { echo '{'; echo menuentry; }\n").unwrap();
        assert_eq!(e[0].selector, "os-id");
    }
    #[test]
    fn numeric_id_uses_index() {
        assert_eq!(
            parse("menuentry 'OS' --id 99 {} ").unwrap()[0].selector,
            "0"
        );
    }
    #[test]
    fn ignores_function_menu_definitions() {
        let es =
            parse("function add_os { menuentry 'Dynamic' {} }\nmenuentry 'Static' {} ").unwrap();
        assert_eq!(es.len(), 1);
        assert_eq!(es[0].selector, "0");
    }
    #[test]
    fn continuation() {
        let cfg = format!("menuentry 'OS' {}{}--id os {{}}", '\\', '\n');
        assert_eq!(parse(&cfg).unwrap()[0].selector, "os");
    }
    #[test]
    fn rejects_duplicate() {
        assert!(parse("menuentry a --id x {}; menuentry b --id x {}").is_err());
    }
}
