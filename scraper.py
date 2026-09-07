import argparse
import csv
import sys
import time
from pathlib import Path

try:
    from seleniumbase import SB
except ImportError:
    print("Please run: pip install seleniumbase")
    sys.exit(1)

# KCMS dataset columns
COLUMNS = [
    "comment_id",
    "text",
    "severity_id",
    "target_id",
    "has_pii",
    "link_flagged",
    "annotator",
    "split",
    "notes",
    "post_text",
    "parent_text",
    "is_reply",
    "created_time",
    "source_page_id",
]

def open_appender(path: Path):
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
    if is_new:
        writer.writeheader()
    return handle, writer

def extract_comments_from_dom(sb):
    js_code = '''
        var results = [];
        var articles = document.querySelectorAll('div[role="article"]');
        
        // Strategy 1: Standard Post extraction
        if (articles.length > 0) {
            articles.forEach((article, index) => {
                // Check if this article is actually a reply
                var aria = article.getAttribute("aria-label");
                if (aria && (aria.toLowerCase().includes("reply") || aria.toLowerCase().includes("replied"))) {
                    return; // Skip this iteration
                }
                
                var textDivs = article.querySelectorAll('div[dir="auto"]');
                var text = "";
                textDivs.forEach(div => {
                    if (div.innerText && div.innerText.trim().length > 0) {
                        text += div.innerText + " ";
                    }
                });
                
                // Aggressive cleaning to remove Facebook UI artifacts
                text = text.replace(/…\s*See more/gi, "");
                text = text.replace(/\.\.\.\s*See more/gi, "");
                text = text.replace(/See Original.*/gi, "");
                text = text.replace(/See translation.*/gi, "");
                text = text.replace(/…\s*មើលបន្ថែម/gi, "");
                text = text.replace(/\.\.\.\s*មើលបន្ថែម/gi, "");
                text = text.replace(/…\s*មើលច្រើនទៀត/gi, "");
                text = text.replace(/\.\.\.\s*មើលច្រើនទៀត/gi, "");
                text = text.replace(/មើលដើម.*/gi, "");
                text = text.replace(/មើលការបកប្រែ.*/gi, "");
                text = text.trim();
                
                if (text.length > 0 && !["Like", "Reply", "Share", "Follow", "ចូលចិត្ត", "ឆ្លើយតប", "ចែករំលែក", "ចែក​រំលែក"].includes(text)) {
                    results.push({
                        "id": "dom_" + text.substring(0, 15).replace(/[^a-zA-Z0-9]/g, "") + "_" + index,
                        "text": text
                    });
                }
            });
        }
        
        // Strategy 2: Reels / Obfuscated DOM fallback
        // If Strategy 1 found nothing, we extract all significant text blocks
        if (results.length < 2) {
            var allTextDivs = document.querySelectorAll('div[dir="auto"], span[dir="auto"]');
            var ignoreList = [
                "Like", "Reply", "Share", "Follow", "See more", "Comment", "Send", "Log In", "Create new account",
                "ចូលចិត្ត", "ឆ្លើយតប", "ការឆ្លើយតប", "ចែករំលែក", "ចែក​រំលែក", "តាមដាន", "មើលបន្ថែម", "មតិយោបល់", "បញ្ជូន", "ចូលគណនី", "បង្កើតគណនីថ្មី"
            ];
            
            allTextDivs.forEach((div, index) => {
                var text = div.innerText ? div.innerText.trim() : "";
                
                // Aggressive cleaning to remove Facebook UI artifacts
                text = text.replace(/…\s*See more/gi, "");
                text = text.replace(/\.\.\.\s*See more/gi, "");
                text = text.replace(/See Original.*/gi, "");
                text = text.replace(/See translation.*/gi, "");
                text = text.replace(/…\s*មើលបន្ថែម/gi, "");
                text = text.replace(/\.\.\.\s*មើលបន្ថែម/gi, "");
                text = text.replace(/…\s*មើលច្រើនទៀត/gi, "");
                text = text.replace(/\.\.\.\s*មើលច្រើនទៀត/gi, "");
                text = text.replace(/មើលដើម.*/gi, "");
                text = text.replace(/មើលការបកប្រែ.*/gi, "");
                text = text.trim();
                
                // Only grab blocks that look like actual user comments/text (> 15 chars)
                if (text.length > 15 && !ignoreList.includes(text)) {
                    // Prevent nested duplicates
                    var isDup = false;
                    for (var i=0; i<results.length; i++) {
                        if (results[i].text.includes(text) || text.includes(results[i].text)) {
                            isDup = true; 
                            break;
                        }
                    }
                    if (!isDup) {
                        results.push({
                            "id": "fbtext_" + text.substring(0, 15).replace(/[^a-zA-Z0-9]/g, "") + "_" + index,
                            "text": text
                        });
                    }
                }
            });
        }
        
        return results;
    '''
    return sb.execute_script(js_code)

def extract_post_urls(sb):
    """Finds all post links on a Facebook Page."""
    js_code = '''
        var links = [];
        document.querySelectorAll('a').forEach(a => {
            var href = a.href;
            if (href && (href.includes('/posts/') || href.includes('/videos/') || href.includes('/permalink/') || href.includes('/reel/'))) {
                // Clean URL by removing query params except for fbid
                var cleanUrl = href.split('?')[0];
                if (!links.includes(cleanUrl)) {
                    links.push(cleanUrl);
                }
            }
        });
        return links;
    '''
    return sb.execute_script(js_code)

def scrape_post_logic(sb, url, extracted_ids, collected_comments, max_comments, log_callback):
    """Scrapes comments from a single post."""
    log_callback(f"\nNavigating to Post: {url}")
    sb.open(url)
    time.sleep(5)
    
    # Try to explicitly open the comment section if it's hidden (e.g. on Reels or Videos)
    log_callback("Attempting to expand comment section if hidden...")
    sb.execute_script(r'''
        var keywords = ["comment", "មតិយោបល់", "បញ្ចេញមតិ", "មតិ"];
        document.querySelectorAll('[role="button"], [aria-label], a, div[dir="auto"]').forEach(btn => {
            var aria = btn.getAttribute("aria-label") || (btn.innerText ? btn.innerText : "");
            if (aria) {
                aria = aria.replace(/[\u200B-\u200D\uFEFF]/g, '').trim().toLowerCase();
                keywords.forEach(kw => {
                    // Click anything that looks like a comment button, but exclude replies and shares
                    if (aria.includes(kw) && !aria.includes("reply") && !aria.includes("ការឆ្លើយតប") && !aria.includes("share")) {
                        btn.click();
                    }
                });
            }
        });
    ''')
    # Wait longer for the Reel side-panel to animate and load comments
    time.sleep(5)
    
    # Force Facebook to show ALL comments instead of 'Most Relevant'
    log_callback("Attempting to sort by 'All comments' to reveal hidden comments...")
    sb.execute_script(r'''
        var triggers = [];
        document.querySelectorAll('span').forEach(el => {
            var t = (el.innerText || "").replace(/[\u200B-\u200D\uFEFF]/g, '').trim().toLowerCase();
            if (t === 'most relevant' || t === 'ដែលពាក់ព័ន្ធបំផុត' || t === 'newest' || t === 'ថ្មីបំផុត' || t === 'top comments') {
                triggers.push(el);
            }
        });
        if (triggers.length > 0) {
            var el = triggers[triggers.length - 1];
            el.click();
            var parent = el.closest('div[role="button"]');
            if (parent) parent.click();
        }
    ''')
    time.sleep(2) # Wait for dropdown menu to appear
    
    sb.execute_script(r'''
        var options = [];
        document.querySelectorAll('span').forEach(el => {
            var t = (el.innerText || "").replace(/[\u200B-\u200D\uFEFF]/g, '').trim().toLowerCase();
            if (t === 'all comments' || t === 'មតិទាំងអស់') {
                options.push(el);
            }
        });
        if (options.length > 0) {
            var opt = options[options.length - 1];
            opt.click();
            var parent = opt.closest('div[role="menuitem"], div[role="button"]');
            if (parent) parent.click();
        }
    ''')
    time.sleep(3) # Wait for comments to reload
    
    scroll_attempts = 0
    no_new_comments_streak = 0
    post_collected_count = 0
    
    # Allow up to 1000 scroll/click attempts to grab "all" comments
    while post_collected_count < max_comments and scroll_attempts < 1000:
        
        # URL Safety Check: Facebook uses infinite scrolling and might silently change 
        # the URL to a new post if we scroll too far down.
        # We must abort immediately if the base URL changes so we don't pollute the CSV.
        current_url = sb.get_current_url()
        base_target = url.split('?')[0].rstrip('/')
        base_current = current_url.split('?')[0].rstrip('/')
        
        if base_target not in base_current:
            log_callback(f"\n[!] WARNING: Facebook auto-navigated to a different post!")
            log_callback(f"[!] Target: {base_target} | Current: {base_current}")
            log_callback("[!] Halting extraction to prevent scraping bad data.")
            break

        # Precise Scrolling: Instead of aggressively scrolling window or divs by 1500px,
        # we find the LAST extracted comment and gently scroll it into view.
        # This prevents overshooting the post and triggering the "Next Post" auto-loader.
        sb.execute_script(r'''
            var articles = document.querySelectorAll('div[role="article"]');
            if (articles.length > 0) {
                var last = articles[articles.length - 1];
                last.scrollIntoView(false); // false aligns to bottom
                
                // Brute-force scroll: force every parent container to its maximum scroll depth
                var p = last.parentElement;
                while (p && p !== document.body) {
                    if (p.scrollHeight > p.clientHeight) {
                        p.scrollTop = p.scrollHeight;
                    }
                    p = p.parentElement;
                }
            } else {
                var textDivs = document.querySelectorAll('div[dir="auto"]');
                if (textDivs.length > 0) {
                    var last = textDivs[textDivs.length - 1];
                    last.scrollIntoView(false);
                    
                    var p = last.parentElement;
                    while (p && p !== document.body) {
                        if (p.scrollHeight > p.clientHeight) {
                            p.scrollTop = p.scrollHeight;
                        }
                        p = p.parentElement;
                    }
                }
            }
        ''')
        time.sleep(2)
        
        sb.execute_script(r'''
            // Target all common clickable elements in Facebook's DOM
            document.querySelectorAll('div[role="button"], a, span, div[dir="auto"]').forEach(btn => {
                // PREVENT DOUBLE-CLICK BUG: If this element is inside a button, don't click both!
                if ((btn.tagName === 'SPAN' || btn.tagName === 'DIV') && btn.closest('[role="button"], a') && btn.closest('[role="button"], a') !== btn) {
                    return;
                }

                // Remove zero-width spaces and clean text
                var t = (btn.innerText || "").replace(/[\u200B-\u200D\uFEFF]/g, '').trim().toLowerCase();
                if (t.length > 0) {
                    // Revert auto-translations back to the original language (e.g. Khmer)
                    if (t.startsWith('see original') || t.startsWith('មើលដើម')) {
                        btn.click();
                    }
                
                    // Click "See more" to expand long comments, and "View comments" to load more
                    if (t === 'see more' || t.includes('view more') || t === 'view previous comments' || (t.includes('comments') && !t.includes('reply')) || 
                        t.includes('មើលបន្ថែម') || t.includes('អានបន្ថែម') || t.includes('មើលច្រើនទៀត') || t.includes('ផ្សេងទៀត') ||
                        t.includes('មើលមតិ') || t.includes('មតិច្រើនទៀត') ||
                        (t.includes('មតិយោបល់') && !t.includes('ការឆ្លើយតប') && !t.includes('ឆ្លើយតប'))) {
                        if (t.length < 80) {
                            btn.click();
                        }
                    }
                }
            });
        ''')
        # Wait 4 seconds for Facebook's servers to respond and swap the DOM text
        time.sleep(4)
        
        raw_comments = extract_comments_from_dom(sb)
        new_count = 0
        for c in raw_comments:
            if c["id"] not in extracted_ids:
                extracted_ids.add(c["id"])
                collected_comments.append({
                    "comment_id": c["id"],
                    "text": c["text"].replace("\n", " "),
                    "severity_id": "",
                    "target_id": "",
                    "has_pii": "",
                    "link_flagged": "",
                    "annotator": "",
                    "split": "",
                    "notes": "",
                    "post_text": "",
                    "parent_text": "",
                    "is_reply": False,
                    "created_time": "",
                    "source_page_id": "",
                })
                new_count += 1
                post_collected_count += 1
                log_callback(f"Scraped comment: {c['text'][:50]}...")
                
                if post_collected_count >= max_comments:
                    break
                    
        if new_count == 0:
            no_new_comments_streak += 1
            if no_new_comments_streak >= 5: # Increased from 3 to 5 to tolerate slow network loads
                log_callback("No new comments loading. Reached the end of this post.")
                break
        else:
            no_new_comments_streak = 0
            
        scroll_attempts += 1

def run_login(fb_email: str, fb_pass: str, headless: bool = True, log_callback=print):
    """Standalone function to log into Facebook and save the session."""
    user_data_dir = str(Path(__file__).parent / "fb_profile")
    try:
        with SB(uc=True, user_data_dir=user_data_dir, headless=headless) as sb:
            log_callback("\n[!] Opening Facebook Login page...")
            sb.open("https://www.facebook.com/login")
            
            time.sleep(3)
            
            if sb.is_element_visible('input[name="email"]'):
                log_callback("[!] Typing credentials...")
                sb.type('input[name="email"]', fb_email)
                # Pressing 'Enter' (\n) is much more reliable than trying to click Facebook's constantly changing login button
                sb.type('input[name="pass"]', fb_pass + '\n')
                log_callback("[!] Submitted login form. Waiting for authentication...")
                
                wait_time = 0
                while sb.is_element_visible('input[name="email"]') and wait_time < 30:
                    time.sleep(2)
                    wait_time += 2
                
                if wait_time < 30:
                    log_callback("\n[+] Successfully logged into Facebook!")
                    time.sleep(2)
                    try:
                        sb.save_cookies(name="fb_cookies.txt")
                    except Exception as e:
                        pass
                    log_callback("[+] Session saved. You can now use the scraping tabs.")
                    time.sleep(3)
                else:
                    log_callback("\n[-] Login failed or timed out. Please check your credentials or log in manually.")
            else:
                log_callback("\n[+] You are already logged in!")
    except Exception as e:
        log_callback(f"\n[-] Critical error during login: {str(e)}")

def run_scraper(mode: str, url: str, max_comments: int, max_posts: int, out_path: str, headless: bool = True, log_callback=print):
    out_path_obj = Path(out_path)
    extracted_ids = set()
    collected_comments = []

    log_callback(f"Starting {mode.upper()} scraper for: {url}")
    log_callback("WARNING: Using this on your personal account risks a ban.")
    
    user_data_dir = str(Path(__file__).parent / "fb_profile")
    
    try:
        # We use headless=headless to hide the browser window if requested
        with SB(uc=True, user_data_dir=user_data_dir, headless=headless) as sb:
            # Force a large desktop resolution so headless mode doesn't trigger mobile layouts 
            # which hides the comment buttons on Reels
            try:
                sb.set_window_size(1920, 1080)
            except Exception:
                pass
                
            # Load cookies for ultra-reliable session persistence
            try:
                sb.open("https://www.facebook.com") # Must be on domain to load cookies
                time.sleep(1)
                sb.load_cookies(name="fb_cookies.txt")
                sb.refresh_page() # Apply cookies
                time.sleep(2)
            except Exception:
                pass
                
            sb.open(url)
            
            # Wait a moment for the page to render
            time.sleep(4)
            
            # Intelligently detect if Facebook is asking for a login
            # Facebook usually shows an email/password form or a 'login' URL
            if sb.is_element_visible('input[name="email"]') or sb.is_element_visible('input[name="pass"]') or "login" in sb.get_current_url().lower():
                log_callback("\n[!] Login Wall Detected.")
                
                if headless:
                    log_callback("[!] Cannot manually log in because the browser is hidden!")
                    log_callback("[!] Please stop the scraper and use the 'Facebook Login' tab on the sidebar to authenticate first.")
                    return
                else:
                    log_callback("[!] Please log into Facebook in the browser window.")
                    log_callback("[!] The scraper is paused and waiting for you to log in (up to 5 minutes)...")
                    
                    wait_time = 0
                    # Wait until the email input disappears, meaning they logged in or closed it
                    while (sb.is_element_visible('input[name="email"]') or "login" in sb.get_current_url().lower()) and wait_time < 300:
                        time.sleep(2)
                        wait_time += 2
                        
                    if wait_time < 300:
                        log_callback("\n[+] Login successful! Resuming automated extraction...")
                        time.sleep(5) # Let the page redirect and settle
                    else:
                        log_callback("\n[-] Timed out waiting for login. Continuing anyway...")
            else:
                log_callback("\n[+] Session active. No login required.")
            
            if mode == "post":
                scrape_post_logic(sb, url, extracted_ids, collected_comments, max_comments, log_callback)
                
            elif mode == "page":
                log_callback("\nScrolling down the Page timeline to discover posts...")
                # Dynamically scroll to find the requested number of posts
                last_height = sb.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                post_urls = []
                
                # Maximum absolute limit of scrolls just in case to prevent infinite loops (e.g. 500 scrolls)
                while len(post_urls) < max_posts and scroll_attempts < min(500, max_posts * 3):
                    sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)
                    
                    new_height = sb.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        # Re-try in case of slow network
                        time.sleep(2)
                        new_height = sb.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            log_callback("Reached the bottom of the page (or Facebook stopped loading).")
                            break
                            
                    last_height = new_height
                    scroll_attempts += 1
                    
                    post_urls = extract_post_urls(sb)
                    
                log_callback(f"Discovered {len(post_urls)} posts on this page after scrolling.")
                
                # Limit to the max_posts requested by user
                post_urls = post_urls[:max_posts]
                log_callback(f"Limiting to the first {len(post_urls)} posts based on your settings.")
                
                for post_url in post_urls:
                    scrape_post_logic(sb, post_url, extracted_ids, collected_comments, max_comments, log_callback)

            log_callback(f"\nFinished scraping! Collected {len(collected_comments)} comments in total.")
    except Exception as e:
        log_callback(f"Error during scraping: {str(e)}")
        return

    if collected_comments:
        handle, writer = open_appender(out_path_obj)
        for row in collected_comments:
            writer.writerow(row)
        handle.close()
        log_callback(f"Successfully saved {len(collected_comments)} comments to {out_path_obj.name}")
    else:
        log_callback("No comments found. You may need to log in or try a different URL.")
