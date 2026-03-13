# 🌅 SoulStart Devotion
**Faith to Rise, Grace to Rest — A Silent SoulConnect Ministry Project**

SoulStart Devotion is a comprehensive web-based devotional platform designed to inspire daily reflection and faith-centered study. It provides morning and evening devotions, Bible study resources, prayer requests, volunteer opportunities, and community features — all accessible online with a focus on inclusivity for the Deaf community.

---

## 🚀 Features

- 🌄 **Daily Devotions** — Morning (Sunrise) and Evening (Sunset) reflections with scripture, meaning, and prayer
- 📖 **Bible Study Hub** — Interactive lessons and study series for spiritual growth
- 🙏 **Prayer Requests** — Community prayer submission and admin management
- 💬 **WhatsApp Integration** — Share daily devotions and build community
- 💚 **Volunteer & Donation Pages** — Support the ministry through service and giving
- 🔐 **Admin Dashboard** — Private access for content management and community oversight
- 📚 **Blog System** — Monthly themes and spiritual encouragement
- 🎯 **Theme Verses** — Curated scripture with visual elements
- 📱 **Mobile-Responsive** — Optimized for all devices
- 🤟 **Accessibility-Focused** — Designed with Deaf community needs in mind

---

## 🏗️ Tech Stack

- **Backend:** Flask (Python 3.11+)
- **Frontend:** HTML5 / Jinja2 / CSS3 (Custom SoulStart Theme)
- **Database:** JSON file storage for devotions, prayers, and content
- **Security:** Flask-WTF CSRF protection, Flask-Limiter rate limiting
- **Deployment:** Render / GitHub Pages
- **Automation:** WhatsApp broadcasting, content ingestion tools

---

## ⚙️ Local Setup Guide

### Prerequisites
- Python 3.11 or higher
- Git
- Virtual environment support

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/SCWB2024/SilentSoulConnectMinistry.git
   cd "SoulStart Devotion"
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv soulstart
   soulstart\Scripts\activate

   # macOS/Linux
   python -m venv soulstart
   source soulstart/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables** (optional for development)
   ```bash
   # Create a .env file or set these in your environment
   export SECRET_KEY="your-secure-random-key-here"
   export ADMIN_EMAIL="your-admin-email@example.com"
   export ADMIN_PASSWORD="your-secure-admin-password"
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open your browser**
   - Navigate to: `http://127.0.0.1:5000`
   - The app will auto-open in your default browser

---

## 🌐 Deployment

### Render (Recommended)
1. Connect your GitHub repository to Render
2. Set build settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
3. Add environment variables:
   - `SECRET_KEY` (required)
   - `ADMIN_EMAIL` (optional)
   - `ADMIN_PASSWORD` (optional)
   - `FORCE_HTTPS=1` (for production)

### Environment Variables
```bash
# Required for production
SECRET_KEY=your-secure-random-string-here

# Admin access (optional)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=secure-password

# Social links (optional)
FACEBOOK_URL=https://facebook.com/your-page
LINKEDIN_URL=https://linkedin.com/company/your-org
WHATSAPP_GROUP_LINK=https://chat.whatsapp.com/your-group

# Content settings (optional)
SITE_THEME="Your Custom Theme"
PAYPAL_LINK=https://paypal.me/your-link
```

---

## 📁 Project Structure

```
SoulStart Devotion/
│
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── requirements-local.txt      # Local development dependencies
├── README.md                   # This file
├── render.yaml                 # Render deployment config
├── .env.example               # Environment variables template
│
├── soulstart/                  # Virtual environment
├── __pycache__/               # Python cache files
│
├── data/                       # JSON data storage
│   ├── devotions/              # Year-based devotion files
│   │   ├── devotions_2025.json
│   │   └── devotions_2026.json
│   ├── blog_posts.json         # Blog content
│   ├── donations.json          # Donation records
│   ├── feedback.json           # User feedback
│   ├── prayer_requests.json    # Prayer submissions
│   ├── prayers.json            # Prayer content
│   ├── studies.json            # Study metadata
│   ├── verses.json             # Theme verses
│   └── volunteers.json         # Volunteer signups
│
├── devotions_legacy/           # Legacy devotion files (by month)
│   ├── August/                 # Historical data
│   ├── September/
│   └── ...
│
├── soulstart/                  # Application package
│   ├── static/                 # CSS, images, downloads
│   │   ├── css/theme.css       # Main stylesheet
│   │   ├── img/                # Images and assets
│   │   └── study/              # Study materials
│   ├── templates/              # Jinja2 templates
│   │   ├── base.html           # Base template
│   │   ├── home.html           # Homepage
│   │   ├── devotion.html       # Devotion pages
│   │   └── admin/              # Admin templates
│   ├── routes.py               # Additional routes (unused)
│   ├── study.py                # Study blueprint (unused)
│   └── utils/                  # Utility functions
│
├── scripts/                    # Automation scripts
│   ├── broadcast_daily.py      # Daily broadcast automation
│   ├── migrate_2025_to_year_json.py
│   ├── split_week_doc.py       # Document processing
│   └── whatsapp_auto.py        # WhatsApp integration
│
├── templates/                  # Main templates
│   ├── base.html               # Base layout
│   ├── home.html               # Homepage
│   ├── devotion.html           # Devotion display
│   ├── prayer.html             # Prayer request form
│   ├── about.html              # About page
│   ├── donation.html           # Donation page
│   ├── volunteer.html          # Volunteer signup
│   ├── verses.html             # Theme verses
│   ├── login.html              # Admin login
│   ├── admin/                  # Admin dashboard templates
│   └── study/                  # Study page templates
│
├── tools/                      # Development utilities
│   ├── add_nonce.py            # Content processing
│   └── ingest.py               # Data ingestion
│
├── exports/                    # Export utilities
├── logs/                       # Application logs
└── private/                    # Private documentation
```

---

## 🔧 Development

### Adding New Devotions
1. Add content to `data/devotions/devotions_YYYY.json`
2. Follow the unified schema format
3. Include morning/night slots with scripture, meaning, and prayer

### Admin Access
- Visit `/login` to access admin dashboard
- Requires `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables
- Admin features: prayer management, blog posting, WhatsApp broadcasting

### Content Management
- **Devotions**: JSON files in `data/devotions/`
- **Blog Posts**: Managed through admin interface
- **Theme Verses**: JSON configuration with image assets
- **Studies**: Template-based with metadata

---

## 🤝 Contributing

This is a ministry project focused on spiritual content. For contributions:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 👩🏽‍💻 Author & Ministry
## 👩🏽‍💻 Author & Ministry
**Evangelist Sandra White-Belgrave**
Founder of *Silent SoulConnect Ministry*

- 📧 [sscministry@outlook.com](mailto:sscministry@outlook.com)
- 🌍 [Facebook.com/SilentSoulConnect](https://www.facebook.com/profile.php?id=61585837505269)
- 💼 [LinkedIn Company Page](https://www.linkedin.com/company/silentsoulconnect)

### 🕊️ Weekly Bible Study
- **Time:** Sundays, 7:00 PM EST
- **Platform:** [Zoom Meeting](https://zoom.us/j/88914147780)
- **Focus:** Inclusive community Bible study

> *"Let faith rise like the sunrise, and peace rest like the sunset."* ☀️🌙

---

## 📄 License
This project is open for ministry and non-commercial use.
© 2025 Silent SoulConnect Ministry — All Rights Reserved.

---

## 🙏 Acknowledgments
Built with love for the glory of God and service to His people. Special thanks to the Deaf community and all who contribute to making faith accessible to everyone.
