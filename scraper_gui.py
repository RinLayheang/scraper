import customtkinter as ctk
import threading
from pathlib import Path

# Import our custom scraping functions
from scraper import run_scraper, run_login

# Set the modern theme globally
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class ScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DataForge Scraper")
        self.geometry("950x650")
        
        # Configure a 1x2 grid layout (Sidebar and Main Area)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1) # Push everything below row 4 to the bottom
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="KCMS Scraper", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.login_btn = ctk.CTkButton(self.sidebar, text="Facebook Login", anchor="w",
                                       command=self.show_login_mode, height=40, font=ctk.CTkFont(weight="bold"))
        self.login_btn.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.post_btn = ctk.CTkButton(self.sidebar, text="Post Scraper", anchor="w", 
                                      command=self.show_post_mode, height=40, font=ctk.CTkFont(weight="bold"))
        self.post_btn.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.page_btn = ctk.CTkButton(self.sidebar, text="Page Scraper", anchor="w",
                                      command=self.show_page_mode, height=40, font=ctk.CTkFont(weight="bold"))
        self.page_btn.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        # Global Headless Toggle in Sidebar
        self.headless_var = ctk.BooleanVar(value=True)
        self.headless_switch = ctk.CTkSwitch(self.sidebar, text="Hide Browser", variable=self.headless_var, font=ctk.CTkFont(weight="bold"))
        self.headless_switch.grid(row=4, column=0, padx=20, pady=30, sticky="ew")
        
        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=40, pady=40)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(5, weight=1) # Make the console text box expand vertically
        
        # Title
        self.title_label = ctk.CTkLabel(self.main_frame, text="Scrape Single Post", font=ctk.CTkFont(size=28, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        # URL Input
        self.url_input = ctk.CTkEntry(self.main_frame, placeholder_text="Enter Facebook URL...", height=45, font=ctk.CTkFont(size=14))
        self.url_input.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        
        # --- Settings Frame ---
        self.settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.grid(row=2, column=0, sticky="ew", pady=(0, 30))
        self.settings_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Max Comments
        self.max_comm_label = ctk.CTkLabel(self.settings_frame, text="Max Comments per Post:")
        self.max_comm_label.grid(row=0, column=0, sticky="w")
        self.max_comm_input = ctk.CTkEntry(self.settings_frame, width=120)
        self.max_comm_input.insert(0, "50")
        self.max_comm_input.grid(row=1, column=0, sticky="w", padx=(0, 20))
        
        # Max Posts (hidden by default)
        self.max_posts_label = ctk.CTkLabel(self.settings_frame, text="Max Posts:")
        self.max_posts_input = ctk.CTkEntry(self.settings_frame, width=120)
        self.max_posts_input.insert(0, "10")
        # Grid placement happens dynamically in show_page_mode
        
        # Out Path
        self.out_label = ctk.CTkLabel(self.settings_frame, text="Output CSV Path", text_color="gray70")
        self.out_label.grid(row=0, column=2, sticky="w")
        self.out_input = ctk.CTkEntry(self.settings_frame, width=200)
        self.out_input.insert(0, "raw_data/comments.csv")
        self.out_input.grid(row=1, column=2, sticky="ew")
        
        # --- Credentials Frame ---
        self.cred_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        # Hidden by default, only shown in login mode
        self.cred_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Email
        self.email_label = ctk.CTkLabel(self.cred_frame, text="Facebook Email (Optional Auto-Login)", text_color="gray70")
        self.email_label.grid(row=0, column=0, sticky="w")
        self.email_input = ctk.CTkEntry(self.cred_frame, height=35, placeholder_text="example@email.com")
        self.email_input.grid(row=1, column=0, sticky="ew", padx=(0, 20))
        
        # Password
        self.pass_label = ctk.CTkLabel(self.cred_frame, text="Facebook Password (Optional)", text_color="gray70")
        self.pass_label.grid(row=0, column=1, sticky="w")
        self.pass_input = ctk.CTkEntry(self.cred_frame, height=35, show="*")
        self.pass_input.grid(row=1, column=1, sticky="ew")
        
        # Start Button
        self.start_btn = ctk.CTkButton(self.main_frame, text="Start Extraction", height=50, 
                                       font=ctk.CTkFont(size=15, weight="bold"), command=self.start_scraping)
        self.start_btn.grid(row=3, column=0, sticky="ew", pady=(0, 20))
        
        # Console
        self.console_label = ctk.CTkLabel(self.main_frame, text="Live Console Output", font=ctk.CTkFont(weight="bold"))
        self.console_label.grid(row=4, column=0, sticky="w", pady=(0, 5))
        
        self.console = ctk.CTkTextbox(self.main_frame, font=ctk.CTkFont(family="Consolas", size=13), 
                                      fg_color="#0d1117", text_color="#3fb950", wrap="word")
        self.console.grid(row=5, column=0, sticky="nsew")
        self.console.insert("0.0", "> Ready. Select a mode on the left and enter a URL.\n")
        
        # Default state setup
        # Initialize default view
        self.show_login_mode()

    def show_post_mode(self):
        self.current_mode = "post"
        self.title_label.configure(text="Scrape Single Post")
        
        self.url_input.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        self.settings_frame.grid(row=2, column=0, sticky="ew", pady=(0, 30))
        self.cred_frame.grid_forget()
        
        self.url_input.configure(placeholder_text="https://www.facebook.com/share/p/...")
        
        # Hide Max Posts setting
        self.max_posts_label.grid_forget()
        self.max_posts_input.grid_forget()
        
        # Update sidebar button active states
        self.post_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
        self.page_btn.configure(fg_color="transparent")
        self.login_btn.configure(fg_color="transparent")
        
        self.start_btn.configure(text="Start Extraction")

    def show_page_mode(self):
        self.current_mode = "page"
        self.title_label.configure(text="Scrape Entire Page")
        
        self.url_input.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        self.settings_frame.grid(row=2, column=0, sticky="ew", pady=(0, 30))
        self.cred_frame.grid_forget()
        
        self.url_input.configure(placeholder_text="https://www.facebook.com/TargetPage")
        
        # Show Max Posts setting in the middle column
        self.max_posts_label.grid(row=0, column=1, sticky="w")
        self.max_posts_input.grid(row=1, column=1, sticky="ew", padx=(0, 20))
        
        # Update sidebar button active states
        self.page_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
        self.post_btn.configure(fg_color="transparent")
        self.login_btn.configure(fg_color="transparent")
        
        self.start_btn.configure(text="Start Extraction")
        
    def show_login_mode(self):
        self.current_mode = "login"
        self.title_label.configure(text="Facebook Login Setup")
        
        # Hide scraping inputs
        self.url_input.grid_forget()
        self.settings_frame.grid_forget()
        
        # Show credentials inputs
        self.cred_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        
        # Update sidebar button active states
        self.login_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
        self.post_btn.configure(fg_color="transparent")
        self.page_btn.configure(fg_color="transparent")
        
        self.start_btn.configure(text="Login to Facebook")
        
    def log(self, text):
        # We must use .after() to safely update the GUI from the background thread
        self.after(0, self._log_safe, text)
        
    def _log_safe(self, text):
        self.console.insert("end", text + "\n")
        self.console.see("end")

    def scraping_finished(self):
        self.start_btn.configure(state="normal", text="Start Extraction")
        self.log("> Task completed.")

    def start_scraping(self):
        headless = self.headless_var.get()
        
        if self.current_mode == "login":
            fb_email = self.email_input.get().strip()
            fb_pass = self.pass_input.get().strip()
            if not fb_email or not fb_pass:
                self.log("> [ERROR] Both email and password are required for login.")
                return
            
            self.start_btn.configure(state="disabled", text="Logging in...")
            self.log("\n" + "="*50)
            self.log("> Initiating LOGIN protocol...")
            if headless:
                self.log("> Running in STEALTH (headless) mode. The browser will be hidden.")
                
            threading.Thread(target=self.run_login_worker, args=(fb_email, fb_pass, headless), daemon=True).start()
            return
            
        url = self.url_input.get().strip()
        if not url:
            self.log("> [ERROR] URL cannot be empty.")
            return
            
        try:
            max_comments = int(self.max_comm_input.get())
            max_posts = int(self.max_posts_input.get()) if self.current_mode == "page" else 1
        except ValueError:
            self.log("> [ERROR] Max Comments and Max Posts must be valid numbers.")
            return
            
        out_path = self.out_input.get().strip()
        
        # Disable start button
        self.start_btn.configure(state="disabled", text="Scraping in progress...")
        
        self.log("\n" + "="*50)
        self.log(f"> Initiating {self.current_mode.upper()} protocol...")
        
        headless = self.headless_var.get()
        if headless:
            self.log("> Running in STEALTH (headless) mode. The browser will be hidden.")
        
        # Start the scraper in a background thread to prevent the GUI from freezing
        threading.Thread(
            target=self.run_worker, 
            args=(self.current_mode, url, max_comments, max_posts, out_path, headless), 
            daemon=True
        ).start()

    def run_worker(self, mode, url, max_comments, max_posts, out_path, headless):
        try:
            run_scraper(mode, url, max_comments, max_posts, out_path, headless=headless, log_callback=self.log)
        except Exception as e:
            self.log(f"Critical error: {str(e)}")
        finally:
            self.after(0, self.scraping_finished)
            
    def run_login_worker(self, fb_email, fb_pass, headless):
        try:
            run_login(fb_email, fb_pass, headless=headless, log_callback=self.log)
        except Exception as e:
            self.log(f"Critical error: {str(e)}")
        finally:
            self.after(0, self.scraping_finished)

if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()
