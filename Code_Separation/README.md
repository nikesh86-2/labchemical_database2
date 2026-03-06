# Chemical Inventory Manager

A small desktop application for maintaining a laboratory chemical inventory.
Scans bottle labels via OCR, enriches entries with PubChem data, stores everything
in a local SQLite database and provides a simple PyQt5 interface with search,
editing and low‑stock email alerts.

---

## 🚀 Features

- Add / edit / delete chemicals manually or by processing image folders
- Automatic CAS/catalog detection with OCR and PubChem lookup
- Inline quantity adjustment (`Use Bottle`) and low‑stock notification
- Search by name, common name, CAS number or catalog number
- Configurable email alerts via SMTP
- Login screen with changeable admin password
- Read‑only mode support via file locking

---

## 📁 Project structure

```
.
├── config.py           # DB file name
├── dblock.py           # SQLite lock helper
├── database.py         # schema and save/merge logic
├── chemical_dialog.py  # entry dialog for manual additions
├── ui_mainwindow.py    # main PyQt5 window and UI logic
├── ocr_utils.py        # EasyOCR + PubChem helpers
├── login_dialog.py     # admin login / password change
├── stockmail.py        # low‑stock check & email alert
├── mail_config.py      # EMAIL_USER / EMAIL_PASS
├── main.py             # launcher
├── requirements.txt    # Python dependencies
└── README.md
```

---

## 🛠️ Requirements

- Python 3.10+
- [PyQt5](https://pypi.org/project/PyQt5/)
- [Pillow](https://pypi.org/project/Pillow/)
- [easyocr](https://pypi.org/project/easyocr/)
- [pubchempy](https://pypi.org/project/pubchempy/)
- `numpy`

(Optional) SMTP access to send emails.  A graphical card reader may be
required for some EasyOCR backends.

Install dependencies using:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ⚙️ Configuration

- `config.py` – path to the SQLite file (`chemicals.db` by default).
- `mail_config.py` – define `EMAIL_USER` and `EMAIL_PASS` for SMTP.  These
  may also be supplied via the environment variables `EMAIL_USER` and
  `EMAIL_PASS` (preferred for security).
- `login_credentials.json` – generated automatically; defaults to user
  `admin` with password `chem123`.  Use the **Change Password** button after
  first launch.  You can bypass the file completely by setting the
  environment variables `CHEM_USER` and `CHEM_PASS`.

> 🔒 Be sure to add `chemicals.db`, `login_credentials.json`, and any
> credential files to `.gitignore` (a template is provided).

---

## ▶️ Running the app

```bash
python main.py
```

1. Log in with the configured account.
2. Use **Process Image Folder** to scan new bottles.
3. Add or edit entries manually with **Add Compound Manually** or by
   editing table cells.
4. Click **Use Bottle** to decrement quantity; zero quantities
   trigger an alert email if credentials are set.

---

## 🧩 Development

- The database schema lives in `database.py`; adjustments require a migration
  strategy (not currently implemented).
- OCR regexes and PubChem enrichment are in `ocr_utils.py` (patterns are
  cached for performance).
- UI styling is applied via `styles.py` (JetBrains font + dark theme).

---

## 🤝 Contributing

1. Fork the repo.
2. Create a feature branch.
3. Submit a PR with tests/changes.

---

## 📄 License

*(tbc)*

