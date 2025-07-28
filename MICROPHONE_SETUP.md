# 🎤 Microphone Setup Guide

## Quick Fix for "Failed to access microphone" Error

### Option 1: Use HTTPS (Recommended)

1. **Stop the current server** (Ctrl+C if running)

2. **Start HTTPS version:**
   ```bash
   ./start_web_app_https.sh
   ```

3. **Access via HTTPS:**
   - Open browser to: `https://localhost:8443`
   - You'll see a security warning - click "Advanced" then "Proceed to localhost"

4. **Allow microphone permissions** when prompted

### Option 2: Use Localhost

1. **Access via localhost instead of IP:**
   - Use: `http://localhost:8000` 
   - Instead of: `http://172.18.95.41:8000`

### Option 3: Browser Settings (Chrome)

1. **Open Chrome flags:**
   ```
   chrome://flags/#unsafely-treat-insecure-origin-as-secure
   ```

2. **Add your WSL IP:**
   - Add: `http://172.18.95.41:8000`
   - Click "Enable"
   - Restart Chrome

## Why This Happens

Modern browsers block microphone access on non-HTTPS connections for security reasons, with exceptions for:
- `localhost` and `127.0.0.1` 
- HTTPS connections
- Explicitly allowed origins

## Testing Your Setup

1. **Visit the troubleshooting page:**
   - Go to `/troubleshooting` in your web app
   - Run the built-in tests
   - Follow specific solutions for your issue

2. **Check browser permissions:**
   - Look for microphone icon in address bar
   - Ensure microphone is not blocked

3. **Verify hardware:**
   - Test microphone in other applications
   - Check Windows audio settings

## Browser-Specific Solutions

### Chrome
- Settings → Privacy and security → Site settings → Microphone
- Ensure the site is allowed

### Firefox  
- Preferences → Privacy & Security → Permissions → Microphone
- Click "Settings" to manage permissions

### Edge
- Settings → Site permissions → Microphone
- Manage permissions for the site

## Still Having Issues?

1. **Check the logs** in the terminal where you started the server
2. **Open browser developer tools** (F12) and check for errors
3. **Try a different browser** to isolate the issue
4. **Restart both the server and browser**

## Advanced: Self-Signed Certificate Setup

The HTTPS script automatically generates a self-signed certificate. If you need to customize it:

```bash
# Generate custom certificate
openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes
```

Then restart with `./start_web_app_https.sh`.