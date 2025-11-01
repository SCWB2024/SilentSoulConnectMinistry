# 🌅 SoulStart Devotion  
**Faith to Rise, Grace to Rest — A Silent SoulConnect Ministry Project**

SoulStart Devotion is a web-based devotional platform designed to inspire daily reflection and faith-centered study.  
It includes morning and evening devotions, Bible study resources, prayer requests, volunteer signup, and weekly study themes — all accessible online.

---

## 🚀 Features

- 🌄 **Sunrise & Sunset Devotions** (daily JSON data per month)  
- 📖 **Bible Study Hub** — simple lessons for the Deaf & visual learners  
- 🙏 **Prayer Requests & Feedback Forms**  
- 💬 **WhatsApp Integration** for sharing daily reflections  
- 💚 **Volunteer & Donation Pages**  
- 🔐 **Admin Dashboard** (private access)

---

## 🏗️ Tech Stack

- **Backend:** Flask (Python 3.11 +)  
- **Frontend:** HTML / Jinja2 / CSS (custom SoulStart theme)  
- **Storage:** JSON files for devotions, studies & prayer logs  
- **Deployment:** Render / GitHub  
- **Automation:** WhatsApp Auto-Sender & DOCX ingestion tools

---

## ⚙️ Local Setup Guide

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/soulstart-devotion.git
   cd soulstart-devotion

##2. Create a virtual environment

python -m venv venv
venv\Scripts\activate    # Windows  
source venv/bin/activate # Mac / Linux

##3. Install dependencies

pip install -r requirements.txt

##4. Run the app

python app.py

##5. Open your browser → http://127.0.0.1:5000

🌐 Deploy to Render (Free Hosting)
Click the button below 👇🏽 to deploy directly from GitHub:

When prompted:

Build Command: pip install -r requirements.txt

Start Command: gunicorn app:app

Add Environment Variables:

SECRET_KEY = your-secure-string
FORCE_HTTPS = 1

##Render will assign your public URL, for example:

https://soulstart.onrender.com

**📁 Folder Structure**

SoulStart Devotion/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── static/
│   ├── css/
│   ├── img/
│   └── Spirit Study/
│
├── templates/
│
├── devotions/
│   ├── September/
│   ├── October/
│   ├── November/
│   ├── December/
│   ├── studies.json
│   └── verses.json
│
├── scripts/
│   ├── split_week_doc.py
│   └── whatsapp_auto.py
│
└── tools/
    ├── add_nonce.py
    └── ingest.py

## 👩🏽‍💻 Author
**Evangelist Sandra White-Belgrave**  
Founder of *Silent SoulConnect Ministry*  
📧 [sscministry@outlook.com](mailto:sscministry@outlook.com)  
🌍 [Facebook.com/SilentSoulConnect](#)  

🕊️ **SSCM Nightly Bible Study**  
🕗 *8:00 PM – 9:00 PM (EDT)*  
📺 [Join on Microsoft Teams](https://teams.live.com/meet/9395975292264?p=bofLQhZB3UuY5eeYEY)

> “Let faith rise like the sunrise, and peace rest like the sunset.” ☀️🌙

##🛠️ License
This project is open for ministry and non-commercial use.
© 2025 Silent SoulConnect Ministry — All Rights Reserved.
