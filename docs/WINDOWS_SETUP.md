# 🪟 Windows Port Forwarding Setup for Microphone Access

## 🎯 **Solution for "Permission denied by system" Error**

The microphone access issue occurs because WSL doesn't have direct access to Windows audio devices. The solution is to set up port forwarding so your Windows browser connects to `localhost` (which browsers trust for microphone access).

---

## 🚀 **Quick Setup (Run This First)**

### **Step 1: Run Port Forwarding Script (Windows)**
```powershell
# In Windows PowerShell (Run as Administrator)
# Copy the setup_windows_portforward.ps1 file to Windows, then run:
PowerShell -ExecutionPolicy Bypass -File setup_windows_portforward.ps1
```

### **Step 2: Start WSL Web App**
```bash
# In WSL terminal
cd /home/kiosk_user/kiosk-controlled-speech
./start_web_app_simple.sh
```

### **Step 3: Access from Windows Browser**
Open: **`http://localhost:8000`**

---

## 📋 **Manual Setup (Alternative)**

If you prefer to set up manually:

### **Windows PowerShell (Run as Administrator):**
```powershell
# Remove existing rules
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=127.0.0.1

# Add port forwarding (replace 172.18.95.41 with your WSL IP)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=127.0.0.1 connectport=8000 connectaddress=172.18.95.41

# Verify
netsh interface portproxy show v4tov4

# Add firewall rule
New-NetFirewallRule -DisplayName "WSL Kiosk Speech App" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### **Find Your WSL IP:**
```bash
# In WSL terminal
hostname -I | awk '{print $1}'
```

---

## ✅ **How This Fixes the Issue**

| Before (Broken) | After (Working) |
|----------------|-----------------|
| Windows browser → `http://172.18.95.41:8000` | Windows browser → `http://localhost:8000` |
| ❌ "Insecure origin" - microphone blocked | ✅ "Secure context" - microphone allowed |
| ❌ WSL IP = untrusted by browser | ✅ Localhost = trusted by browser |

---

## 🧪 **Test the Fix**

1. **Open Windows browser to:** `http://localhost:8000`
2. **Click the settings gear** ⚙️ in the bottom right
3. **Click "Test Microphone Access"** button
4. **Should show:** ✅ SUCCESS! Microphone access granted

---

## 🛠️ **Troubleshooting**

### **If Still Not Working:**

1. **Check port forwarding is active:**
   ```powershell
   netsh interface portproxy show v4tov4
   ```

2. **Verify WSL app is running:**
   ```bash
   netstat -tlnp | grep :8000
   ```

3. **Test direct WSL connection:**
   ```bash
   curl http://localhost:8000
   ```

4. **Use troubleshooting page:**
   `http://localhost:8000/troubleshooting`

### **Remove Port Forwarding (If Needed):**
```powershell
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=127.0.0.1
```

---

## 🔒 **Security Notes**

- Port forwarding only works for local connections
- No external network access is opened
- Only redirects `localhost:8000` to your WSL instance
- Can be easily removed when not needed

---

## 🎉 **Expected Result**

After setup, your workflow will be:

1. **Start WSL app:** `./start_web_app_simple.sh`
2. **Open Windows browser:** `http://localhost:8000`
3. **Click microphone:** 🎤 → Allow permissions
4. **Speak:** Your speech gets transcribed and sent to Ollama
5. **Get response:** LLM responds to your voice input

**The microphone access issue should be completely resolved!** ✨