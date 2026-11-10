/* =========================================================================
   Share — WhatsApp / native share / clipboard helpers for PayCheck.
   All messages are built locally and opened in the user's own apps.
   ========================================================================= */
(() => {
  'use strict';

  const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const Share = {
    canNativeShare() { return typeof navigator !== 'undefined' && !!navigator.share; },

    waUrl(text, phone) {
      const p = phone ? String(phone).replace(/[^\d]/g, '') : '';
      return 'https://wa.me/' + p + '?text=' + encodeURIComponent(text);
    },

    open(text, phone) {
      window.open(this.waUrl(text, phone), '_blank', 'noopener,noreferrer');
    },

    async native(title, text, url) {
      try {
        await navigator.share({ title, text, url: url || location.href });
        return true;
      } catch { return false; }
    },

    async copy(text) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch { ok = false; }
        ta.remove();
        return ok;
      }
    },

    /* --------------------------- message builders ---------------------- */
    receipt(tx, merchant) {
      return [
        `*Payment receipt — ${merchant || 'PayCheck'}*`,
        ``,
        `Payer: ${tx.payee}`,
        `Amount: ${inr(tx.amount)}`,
        `Method: ${tx.method}`,
        `Status: ${String(tx.status || '').toUpperCase()}`,
        tx.utr ? `UTR: ${tx.utr}` : null,
        tx.vpa ? `UPI ID: ${tx.vpa}` : null,
        `Date: ${tx.day} ${tx.time || ''}`.trim(),
        ``,
        `Verified via PayCheck (UPI payment verifier).`
      ].filter(Boolean).join('\n');
    },

    reminder(name, amount, merchant) {
      return [
        `Hello ${name || 'there'},`,
        ``,
        `This is a friendly reminder that a payment of ${inr(amount)} is still *pending* at ${merchant || 'our store'}.`,
        `Please complete it at your convenience — or share the UTR if you have already paid.`,
        ``,
        `Thank you.`
      ].join('\n');
    },

    collect({ merchant, vpa, amount, note }) {
      return [
        `*Pay ${merchant || 'us'}*`,
        ``,
        amount ? `Amount: ${inr(amount)}` : null,
        `UPI ID: ${vpa}`,
        note ? `Note: ${note}` : null,
        ``,
        `Pay using any UPI app (GPay / PhonePe / Paytm) to the UPI ID above.`
      ].filter(Boolean).join('\n');
    },

    verifySummary({ payee, amount, verdict, gatewayStatus, merchant }) {
      const label = verdict === 'ok' ? 'SAFE' : verdict === 'pend' ? 'CAUTION' : 'DANGER';
      return [
        `*Payment check — ${merchant || 'PayCheck'}*`,
        ``,
        `Payer: ${payee}`,
        amount ? `Amount: ${inr(amount)}` : null,
        gatewayStatus ? `Gateway status: ${gatewayStatus}` : null,
        `Result: *${label}*`,
        ``,
        `Checked with PayCheck before handing over goods.`
      ].filter(Boolean).join('\n');
    }
  };

  window.Share = Share;
})();
