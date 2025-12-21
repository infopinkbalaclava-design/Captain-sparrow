# Vision Trainer op Termux (Android)

## Belangrijke beperkingen op Termux ⚠️

Termux is een Android terminal emulator en heeft belangrijke beperkingen:
- **Geen GUI** (tkinter/X11 werkt niet zonder VNC setup)
- **Geen keyboard injection** naar andere apps (Android-beveiliging)
- **Geen screen capture** van andere apps zonder root
- **OpenCV visual matching** is zeer beperkt zonder display server

**Wat WEL werkt:**
- Web panel (API) voor remote control
- Basis Python scripting
- Dependencies installeren en voorbereiden

**Aanbevolen gebruik:**
Gebruik Termux als **server** en bedien het vanaf je Windows PC/laptop via de web interface.

---

## Setup instructies

### 1. Update Termux en installeer basis tools

```bash
pkg update && pkg upgrade -y
pkg install -y python git wget curl
```

### 2. Clone de repository

```bash
cd ~
git clone https://github.com/infopinkbalaclava-design/Captain-sparrow.git
cd Captain-sparrow
```

### 3. Installeer Python dependencies

**Basis dependencies (zonder GUI):**
```bash
pip install --upgrade pip
pip install pillow numpy fastapi uvicorn
```

**OpenCV (optioneel, kan traag zijn):**
```bash
# Waarschuwing: opencv-python is groot en kan errors geven op Termux
pip install opencv-python-headless
```

**NIET installeren op Termux:**
- `keyboard` (werkt niet zonder root)
- `pyautogui` (vereist X11)
- `pytesseract` (vereist system Tesseract binary die moeilijk is op Termux)

### 4. Start alleen de web panel (geen visual trainer)

Omdat GUI en screen capture niet werken, gebruik alleen de web API:

```bash
python scripts/web_panel.py --host 0.0.0.0 --port 8000 --allow-remote --token JOUW_TOKEN_HIER
```

Vervang `JOUW_TOKEN_HIER` met een sterk wachtwoord (bijv. `MySecure123!Token`).

### 5. Vind je lokale IP-adres

```bash
ifconfig wlan0 | grep 'inet '
```

Of:
```bash
ip addr show wlan0 | grep 'inet '
```

Je ziet iets als: `inet 192.168.1.45/24`

### 6. Open de panel vanaf een andere device

Op je Windows PC of andere telefoon, open browser:
```
http://192.168.1.45:8000/?token=JOUW_TOKEN_HIER
```

---

## API endpoints (gebruik vanaf andere device)

**Status ophalen:**
```bash
curl http://192.168.1.45:8000/status?token=JOUW_TOKEN_HIER
```

**Templates ophalen:**
```bash
curl http://192.168.1.45:8000/templates?token=JOUW_TOKEN_HIER
```

**Toggle runner:**
```bash
curl -X POST http://192.168.1.45:8000/toggle?token=JOUW_TOKEN_HIER
```

---

## Wat NIET werkt op Termux

❌ **F12 hotkey detection** - geen keyboard hooks zonder root  
❌ **Screen capture van andere apps** - Android security  
❌ **GUI (tkinter)** - geen X11 server standaard  
❌ **Keyboard injection** - kan niet naar andere apps zonder root  
❌ **Template teach mode** - vereist GUI  

---

## Alternatief: gebruik Termux alleen als remote server

**Beste setup:**
1. Draai de volledige Vision Trainer op een Windows PC
2. Start de web panel op Windows: 
   ```cmd
   python scripts\web_panel.py --host 0.0.0.0 --port 8000 --allow-remote --token TOKEN
   ```
3. Bedien vanaf Termux (Android):
   ```bash
   # Vind IP van Windows PC (bijv. 192.168.1.100)
   curl http://192.168.1.100:8000/status?token=TOKEN
   ```

Dit geeft je volledige controle zonder de beperkingen van Android.

---

## Troubleshooting

**Port geblokkeerd:**
```bash
# Kies andere port
python scripts/web_panel.py --host 0.0.0.0 --port 8080 --allow-remote --token TOKEN
```

**Module niet gevonden:**
```bash
pip list  # check geïnstalleerde packages
pip install --upgrade <package_name>
```

**Kan niet verbinden vanaf ander device:**
- Controleer of firewall op Termux-device actief is (meestal niet)
- Zorg dat beide devices op hetzelfde WiFi-netwerk zitten
- Controleer IP met `ifconfig` of `ip addr`

**Import errors (libGL, etc):**
Dit is normaal op Termux zonder GUI. De web panel zou moeten werken, maar visual matching niet.

---

## Samenvatting

✅ **Op Termux:** Draai web panel als server  
✅ **Op Windows/Linux:** Draai volledige Vision Trainer + web panel  
✅ **Bedien:** Via browser of curl vanaf elk device op het netwerk  

Voor volledige functionaliteit (GUI, screen capture, keyboard injection): **gebruik Windows of Linux met desktop environment**.
