# TWA (Trusted Web Activity) Setup — Google Play Console

Wrap the DMS PWA in a native Android shell and publish on the Google Play Store.

---

## Prerequisites

- **Android Studio** (latest stable) — [download](https://developer.android.com/studio)
- **Java 17+** (bundled with Android Studio)
- **Google Play Console account** ($25 one-time registration) — [console](https://play.google.com/console)
- **DMS frontend** deployed at a public HTTPS domain with a valid SSL certificate

---

## Step 1: Verify PWA readiness

The frontend already has everything TWA needs. Confirm by running Lighthouse in Chrome:

```
chrome://inspect  →  select your deployed site  →  Lighthouse  →  PWA
```

| Requirement | Status |
|------------|--------|
| Service worker registered | ✓ (`dist/sw.js`) |
| Web app manifest with icons | ✓ (192, 512, maskable) |
| HTTPS only | ✓ (nginx SSL) |
| `start_url` points to root | ✓ (`/`) |
| `display: standalone` | ✓ |
| `scope: /` | ✓ |

---

## Step 2: Create the Android app in Android Studio

### 2.1 Generate a keystore (one time)

A keystore signs your APK. The same keystore must be used for every update.

```bash
keytool -genkey -v -keystore dms-upload-keystore.jks \
  -alias dms-key \
  -keyalg RSA -keysize 2048 -validity 10000
```

Store this keystore in a **safe, backed-up location** — you cannot update the app without it.

### 2.2 Create a new Android project

1. Open Android Studio → **New Project** → **Empty Views Activity**
2. Configure:
   - **Name**: `DMS`
   - **Package name**: `com.kannurvision.pdic.dms`
   - **Language**: `Kotlin`
   - **Minimum SDK**: `API 24 (Android 7.0)`
3. Click **Finish**

### 2.3 Add TWA dependencies

Open `app/build.gradle.kts` and add the TWA dependency:

```kotlin
dependencies {
    implementation("androidx.browser:browser:1.8.0")
    // other dependencies remain
}
```

### 2.4 Set the Android App Links verification

Open `app/src/main/AndroidManifest.xml` and add the `asset_statements` meta-data inside `<application>`:

```xml
<application
    android:allowBackup="true"
    android:icon="@mipmap/ic_launcher"
    android:label="DMS"
    android:theme="@style/Theme.DMS">

    <meta-data
        android:name="asset_statements"
        android:resource="@string/asset_statements" />

    <activity
        android:name=".MainActivity"
        android:exported="true"
        android:launchMode="singleTask">
        <intent-filter android:autoVerify="true">
            <action android:name="android.intent.action.VIEW" />
            <category android:name="android.intent.category.DEFAULT" />
            <category android:name="android.intent.category.BROWSABLE" />
            <data
                android:scheme="https"
                android:host="your-production-domain.com" />
        </intent-filter>
    </activity>
</application>
```

### 2.5 Add asset_statements string

Open `app/src/main/res/values/strings.xml` and add:

```xml
<resources>
    <string name="app_name">DMS</string>
    <string name="asset_statements">
        [{
            \"relation\": [\"delegate_permission/common.handle_all_urls\"],
            \"target\": {
                \"namespace\": \"web\",
                \"site\": \"https://your-production-domain.com\"
            }
        }]
    </string>
</resources>
```

### 2.6 Write the TWA launcher activity

Replace `app/src/main/java/com/kannurvision/pdic/dms/MainActivity.kt`:

```kotlin
package com.kannurvision.pdic.dms

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.browser.customtabs.CustomTabsIntent
import androidx.browser.trusted.LauncherActivityMetadata
import androidx.browser.trusted.TrustedWebActivityIntentBuilder
import androidx.browser.trusted.TrustedWebActivityServiceConnectionManager

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val builder = TrustedWebActivityIntentBuilder(Uri.parse("https://your-production-domain.com"))
            // Optional: set the status bar colour to match theme
            .setToolbarColor(0xFF166534.toInt())

        val customTabsIntent = CustomTabsIntent.Builder().build()
        val twaIntent = builder.build(customTabsIntent)

        // Fallback to browser if TWA is not available
        twaIntent.intent.putExtra(
            "android.support.customtabs.extra.EXTRA_LAUNCH_AS_TRUSTED_WEB_ACTIVITY",
            true
        )

        startActivity(twaIntent.intent)
        finish()
    }
}
```

### 2.7 Build the signed APK

1. In Android Studio: **Build** → **Generate Signed Bundle / APK**
2. Select **APK**
3. Point to your keystore (`dms-upload-keystore.jks`), enter the alias and passwords
4. Select **release** build variant
5. Select signature versions **V1 and V2**
6. Click **Finish**

Output: `app/release/app-release.apk`

---

## Step 3: Digital Asset Links — verify site ownership

TWA requires Google to verify you own the domain. There are **two** files needed.

### 3.1 Server-side `assetlinks.json`

Create `frontend/public/.well-known/assetlinks.json` in the DMS codebase so it gets served at:

```
https://your-production-domain.com/.well-known/assetlinks.json
```

```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.kannurvision.pdic.dms",
      "sha256_cert_fingerprints": [
        "AA:BB:CC:..."
      ]
    }
  }
]
```

Get the SHA-256 fingerprint from your keystore:

```bash
keytool -list -v -keystore dms-upload-keystore.jks -alias dms-key \
  | findstr "SHA256"   # Windows PowerShell
```

Ensure nginx serves it with the correct content type:

```nginx
location = /.well-known/assetlinks.json {
    root /path/to/static;
    add_header Content-Type application/json;
}
```

### 3.2 In-app statement (already added in Step 2.5)

The `asset_statements` string in `strings.xml` tells Android to trust your domain. This is validated against the server-side file.

### 3.3 Verify with Google's tester

After deploying, test at:
[https://developers.google.com/digital-asset-links/tools](https://developers.google.com/digital-asset-links/tools)

Enter your domain and the package name — it should return **"Relation found"**.

---

## Step 4: Create an app signing key in Play Console

Google Play **requires** using Play App Signing for all new apps. This changes how you generate the SHA-256 fingerprint.

### 4.1 Upload your keystore to Play Console

1. Go to [Google Play Console](https://play.google.com/console)
2. **Create app** → fill in:
   - **Name**: DMS
   - **Default language**: English
   - **App or game**: App
   - **Free or Paid**: Free
3. Go to **Release** → **Setup** → **App integrity**
4. Under **App signing by Google Play**, choose:
   - **"Let Google generate and manage your app signing key"** (recommended for new apps)
   - OR **"Use the same key as your upload key"** (advanced)

### 4.2 Get the SHA-256 from Play Console

If you chose Google-managed signing:
1. In **App integrity** → **App signing key certificate** → copy the **SHA-256 fingerprint**
2. This is the fingerprint you put in `assetlinks.json` (not your upload key's fingerprint)

If you chose same key for both:
1. Upload your APK first (see Step 5)
2. Once uploaded, Play Console will show the key certificate
3. Copy the SHA-256 from there

### 4.3 Update the `assetlinks.json`

Go back to the server and update the SHA-256 fingerprint in `.well-known/assetlinks.json` with the one shown in Play Console.

Re-verify with Google's DAL tester.

---

## Step 5: Upload to Google Play Console

### 5.1 Upload the APK

1. In **Play Console**, go to the app → **Release** → **Production**
2. Click **Create new release**
3. Upload `app-release.apk` (signed with upload key)
4. Fill release notes (e.g. "Initial release")

### 5.2 Complete store listing

Go to **Grow** → **Store presence** → **Main store listing**:

| Field | Value |
|-------|-------|
| App name | DMS |
| Short description | Distribution Management System |
| Full description | Manage device distribution, tracking, and approvals for field operators. |
| Screenshots | Minimum 2 phone + 2 tablet screenshots (JPEG, 16:9 or 9:16) |
| Category | Productivity |
| Tags | Distribution, Inventory, Field Service |
| Contact email | admin@yourdomain.com |

### 5.3 Complete the content rating questionnaire

Go to **Policy** → **App content** → **Content ratings** → complete the questionnaire. This app is rated **Everyone** with no mature content.

### 5.4 Submit for review

1. Go back to **Release** → **Production** → **Review release**
2. Ensure all checks pass (app signing, content rating, pricing)
3. Click **Send changes for review**

Google typically takes 1–3 days for the initial review. Subsequent updates are usually faster (hours).

---

## Step 6: Verify on a real device

After the app is approved and published:

1. Install from Play Store on an Android phone (8.0+)
2. Open the app — it should load DMS in full-screen mode (no Chrome URL bar)
3. Confirm:
   - Splash screen shows briefly
   - Login works with credentials
   - Push notifications (if configured) arrive
   - App stays within the DMS domain (external links open in browser)
4. Test on different Android versions (8, 10, 12, 14)

---

## Updating the app

### Web-only changes (no APK rebuild needed)

TWA always loads the latest web content from the server — no Play Store update required for frontend changes.

### Android config changes (keystore, icons, permissions)

1. Make changes in Android Studio
2. **Build** → **Generate Signed Bundle / APK**
3. Upload the new APK in **Play Console** → **Release** → **Production** → **Create new release**
4. Increment the **version code** in `build.gradle.kts`:
   ```kotlin
   android {
       defaultConfig {
           versionCode = 2    // increment with each release
           versionName = "1.1.0"
       }
   }
   ```

### Updating the DIGITAL ASSET LINKS

If you get a new signing key or change the domain:
1. Update `.well-known/assetlinks.json` on the server
2. Update `strings.xml` → `asset_statements`
3. Rebuild and upload
4. Re-verify with Google's DAL tester

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App opens in Chrome browser instead of full-screen | `assetlinks.json` not deployed or wrong SHA-256 — use Play Console's fingerprint |
| "Digital Asset Links verification failed" in Play Console | Ensure `assetlinks.json` is served with `Content-Type: application/json` and is accessible without redirects |
| App shows "No internet" screen | Ensure the URL in `MainActivity.kt` is exactly `https://your-production-domain.com` (no trailing slash, no path) |
| Push notifications not working | Ensure `enableNotifications: true` in the web app manifest has `display: standalone` |
| Play Console rejects APK | Ensure the APK is signed with V1 + V2 signature versions and uses the correct keystore |

---

## Key files summary

| File | Location | Purpose |
|------|----------|---------|
| Keystore | `dms-upload-keystore.jks` | Signs the APK for upload |
| `MainActivity.kt` | `app/src/main/java/.../MainActivity.kt` | TWA launcher that opens the domain |
| `AndroidManifest.xml` | `app/src/main/AndroidManifest.xml` | Intent filter + app links verification |
| `strings.xml` | `app/src/main/res/values/strings.xml` | `asset_statements` for DAL |
| `assetlinks.json` | `frontend/public/.well-known/assetlinks.json` | Server-side verification file |
