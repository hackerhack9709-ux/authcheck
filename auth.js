/* =========================================================================
   Auth — local account + session layer for PayCheck.
   Accounts are stored in localStorage with PBKDF2-SHA256 password hashing
   (Web Crypto). This is a client-side demo: it protects local data across
   users on one device, it is NOT server-grade security.
   ========================================================================= */
(() => {
  'use strict';

  const K_USERS = 'paycheck.users.v1';
  const K_SESSION = 'paycheck.session.v1';
  const ITER = 100000;

  /* ------------------------------ helpers ------------------------------ */
  const enc = new TextEncoder();

  const bytesToHex = (b) => [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  const hexToBytes = (h) => new Uint8Array(h.match(/.{1,2}/g).map((x) => parseInt(x, 16)));
  const randomHex = (n = 16) => bytesToHex(crypto.getRandomValues(new Uint8Array(n)));

  const hasSubtle = !!(window.crypto && window.crypto.subtle && window.crypto.subtle.deriveBits);

  async function hash(password, saltHex) {
    if (hasSubtle) {
      const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
      const bits = await crypto.subtle.deriveBits(
        { name: 'PBKDF2', salt: hexToBytes(saltHex), iterations: ITER, hash: 'SHA-256' },
        key, 256
      );
      return bytesToHex(new Uint8Array(bits));
    }
    // Fallback for non-secure contexts: salted FNV-style stretch. Not strong,
    // but keeps the demo usable when crypto.subtle is unavailable.
    let h1 = 0x811c9dc5, h2 = 0x1000193;
    const s = saltHex + '|' + password;
    for (let r = 0; r < 2000; r++) {
      for (let i = 0; i < s.length; i++) {
        h1 = (h1 ^ s.charCodeAt(i)) * 16777619 >>> 0;
        h2 = (h2 + h1 + r) >>> 0;
      }
    }
    return (h1.toString(16) + h2.toString(16)).padStart(16, '0');
  }

  const readJSON = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
  const writeJSON = (k, v) => localStorage.setItem(k, JSON.stringify(v));

  const users = () => readJSON(K_USERS, []);
  const saveUsers = (u) => writeJSON(K_USERS, u);
  const publicUser = (u) => ({ id: u.id, name: u.name, email: u.email, shop: u.shop, createdAt: u.createdAt });

  /* ------------------------------- seed -------------------------------- */
  function seed() {
    if (users().length) return;
    (async () => {
      const salt = randomHex();
      const pinSalt = randomHex();
      saveUsers([{
        id: 'u_demo',
        name: 'Demo Merchant',
        email: 'demo@paycheck.app',
        shop: 'PayCheck Store',
        salt, pass: await hash('demo1234', salt),
        pinSalt, pin: '',
        createdAt: new Date().toISOString()
      }]);
    })();
  }

  /* -------------------------------- API -------------------------------- */
  const Auth = {
    hasSubtle,
    isSecureContext: hasSubtle,

    current() {
      const s = readJSON(K_SESSION, null);
      if (!s) return null;
      const u = users().find((x) => x.id === s.userId);
      return u ? publicUser(u) : null;
    },

    list() { return users().map(publicUser); },

    async signup({ name, email, shop, password, pin }) {
      name = String(name || '').trim();
      email = String(email || '').trim().toLowerCase();
      if (name.length < 2) throw new Error('Enter your name (at least 2 characters).');
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Enter a valid email address.');
      if (String(password || '').length < 8) throw new Error('Password must be at least 8 characters.');
      if (users().some((u) => u.email === email)) throw new Error('An account with this email already exists.');

      const salt = randomHex();
      const pinSalt = randomHex();
      const u = {
        id: 'u_' + randomHex(6),
        name, email, shop: String(shop || '').trim(),
        salt, pass: await hash(password, salt),
        pinSalt, pin: pin ? await hash(String(pin), pinSalt) : '',
        createdAt: new Date().toISOString()
      };
      saveUsers([...users(), u]);
      writeJSON(K_SESSION, { userId: u.id, at: Date.now() });
      return publicUser(u);
    },

    async signin(email, password) {
      email = String(email || '').trim().toLowerCase();
      const u = users().find((x) => x.email === email);
      if (!u) throw new Error('No account found for this email.');
      const ok = (await hash(String(password || ''), u.salt)) === u.pass;
      if (!ok) throw new Error('Incorrect password. Please try again.');
      writeJSON(K_SESSION, { userId: u.id, at: Date.now() });
      return publicUser(u);
    },

    async verifyPin(userId, pin) {
      const u = users().find((x) => x.id === userId);
      if (!u || !u.pin) return false;
      return (await hash(String(pin || ''), u.pinSalt)) === u.pin;
    },

    hasPin(userId) {
      const u = users().find((x) => x.id === userId);
      return !!(u && u.pin);
    },

    async changePassword(userId, oldPass, newPass) {
      const u = users().find((x) => x.id === userId);
      if (!u) throw new Error('Account not found.');
      if ((await hash(String(oldPass || ''), u.salt)) !== u.pass) throw new Error('Current password is incorrect.');
      if (String(newPass || '').length < 8) throw new Error('New password must be at least 8 characters.');
      const salt = randomHex();
      u.salt = salt; u.pass = await hash(newPass, salt);
      saveUsers(users().map((x) => (x.id === u.id ? u : x)));
    },

    async setPin(userId, pin) {
      const u = users().find((x) => x.id === userId);
      if (!u) throw new Error('Account not found.');
      if (pin && !/^\d{4,6}$/.test(String(pin))) throw new Error('PIN must be 4 to 6 digits.');
      if (!pin) { u.pin = ''; u.pinSalt = ''; }
      else { const s = randomHex(); u.pinSalt = s; u.pin = await hash(String(pin), s); }
      saveUsers(users().map((x) => (x.id === u.id ? u : x)));
    },

    update(userId, patch) {
      const u = users().find((x) => x.id === userId);
      if (!u) throw new Error('Account not found.');
      if (patch.name != null) u.name = String(patch.name).trim() || u.name;
      if (patch.shop != null) u.shop = String(patch.shop).trim();
      saveUsers(users().map((x) => (x.id === u.id ? u : x)));
      return publicUser(u);
    },

    signout() { localStorage.removeItem(K_SESSION); },

    /** Storage key scoping all business data to the signed-in user. */
    dataKey(base, userId) { return `${base}.${userId || 'anon'}`; }
  };

  seed();
  window.Auth = Auth;
})();
