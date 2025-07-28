# 🎤 **MICROPHONE TROUBLESHOOTING GUIDE**

## 🚨 **Current Issue:** "Failed to access microphone. Please allow microphone access in your browser settings."

---

## ✅ **IMMEDIATE SOLUTIONS (Try These First)**

### **1. Use Localhost URL (CRITICAL)**
Instead of IP address, use:
```
http://localhost:8000
```
- Browsers **automatically allow** microphone on localhost
- No special configuration needed
- Works in Chrome, Firefox, Edge, Safari

### **2. Check Your Current URL**
- ❌ **Doesn't work:** `http://172.18.95.41:8000`
- ✅ **Works:** `http://localhost:8000`
- ✅ **Also works:** `http://127.0.0.1:8000`

---

## 🛠️ **DIAGNOSTIC TOOLS (Built-in)**

### **Use the Test Button:**
1. **Open web interface:** `http://localhost:8000`
2. **Click settings gear** ⚙️ (bottom right)
3. **Click "Test Microphone Access"** button
4. **Follow the specific error messages**

### **Use Troubleshooting Page:**
Visit: `http://localhost:8000/troubleshooting`
- Automatic browser compatibility checks
- Permission status detection
- Step-by-step fixes

---

## 🔧 **BROWSER-SPECIFIC FIXES**

### **Chrome:**
1. **Check URL bar** - look for 🔒 or 🎤 icon
2. **Click the icon** → Allow microphone
3. **Alternative:** `chrome://settings/content/microphone`
4. **For WSL IP:** Use `chrome://flags/#unsafely-treat-insecure-origin-as-secure`

### **Firefox:**
1. **Check address bar** for microphone icon
2. **Click icon** → Allow
3. **Settings:** `about:preferences#privacy` → Permissions

### **Edge:**
1. **Address bar microphone icon** → Allow
2. **Settings:** edge://settings/content/microphone

---

## 🖥️ **TECHNICAL DIAGNOSIS**

### **Check Browser Console (F12):**
Look for errors like:
- `NotAllowedError` = Permissions blocked
- `NotFoundError` = No microphone detected
- `NotSupportedError` = Need HTTPS/localhost
- `SecurityError` = Insecure context

### **Verify System Requirements:**
- ✅ Modern browser (Chrome 70+, Firefox 65+, Edge 79+)
- ✅ Microphone connected and working
- ✅ Microphone not muted in Windows
- ✅ No other apps blocking microphone access

---

## 🔒 **SECURITY CONTEXT ISSUES**

Modern browsers block microphone access except for:
- ✅ `https://` websites
- ✅ `localhost` addresses  
- ✅ `127.0.0.1` addresses
- ✅ Explicitly allowed origins

**Your app runs on WSL IP** (like `172.18.95.41`) which browsers consider "insecure" for microphone access.

---

## 🚀 **ALTERNATIVE SOLUTIONS**

### **Option A: Windows Host Proxy**
```powershell
# Run in Windows PowerShell as Administrator
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=127.0.0.1 connectport=8000 connectaddress=172.18.95.41
```
Then access: `http://127.0.0.1:8000`

### **Option B: Chrome Flags**
1. Open: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Add: `http://172.18.95.41:8000`
3. Enable and restart Chrome

### **Option C: HTTPS Setup** (Advanced)
```bash
./start_web_app_https.sh
```
Access: `https://localhost:8443` (accept security warning)

---

## 📋 **STEP-BY-STEP CHECKLIST**

1. ☐ **Stop current server** (Ctrl+C)
2. ☐ **Start server:** `./start_web_app_simple.sh`
3. ☐ **Open browser to:** `http://localhost:8000`
4. ☐ **Click "Test Microphone Access"** in settings
5. ☐ **Allow permissions** when prompted
6. ☐ **Test voice recording** with microphone button
7. ☐ **If still fails:** Check troubleshooting page

---

## 🆘 **STILL NOT WORKING?**

### **Check These:**
- Windows microphone privacy settings
- Antivirus blocking microphone access
- Other apps using microphone exclusively
- Windows audio drivers up to date
- Microphone hardware functioning

### **Test in Different Browser:**
- Try Chrome, Firefox, and Edge
- Use private/incognito mode
- Clear browser cache and data

### **Last Resort:**
```bash
# Restart everything
pkill -f uvicorn
./setup_web_app.sh
./start_web_app_simple.sh
```

---

## 💡 **KEY INSIGHT**

The issue is **almost always** one of these:
1. **Not using localhost** (use `http://localhost:8000`)
2. **Browser permissions** (click microphone icon in address bar)
3. **System microphone** (check Windows audio settings)

**99% of cases are solved by using the localhost URL!** 🎯