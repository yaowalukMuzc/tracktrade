/** Outgoing email (SMTP; Mailpit in dev). Templates are bilingual and follow the user's locale. */
import nodemailer from 'nodemailer'
import type { AuthConfig } from './config.js'

export interface Mail {
  to: string
  subject: string
  text: string
  html: string
}

export interface Mailer {
  send(mail: Mail): Promise<void>
}

export function smtpMailer(config: AuthConfig): Mailer {
  const transport = nodemailer.createTransport({
    host: config.smtp.host,
    port: config.smtp.port,
    secure: config.smtp.secure,
    auth: config.smtp.user ? { user: config.smtp.user, pass: config.smtp.password } : undefined,
  })
  return {
    async send(mail) {
      await transport.sendMail({ from: config.mailFrom, ...mail })
    },
  }
}

type Locale = 'th' | 'en'

const RESET_COPY: Record<Locale, { subject: string; greeting: (name: string) => string; body: string; action: string; ignore: string }> = {
  th: {
    subject: 'ตั้งรหัสผ่านใหม่ — TrackTrade',
    greeting: (name) => `สวัสดี ${name}`,
    body: 'เราได้รับคำขอตั้งรหัสผ่านใหม่สำหรับบัญชี TrackTrade ของคุณ ลิงก์นี้ใช้ได้ครั้งเดียวและหมดอายุใน 1 ชั่วโมง',
    action: 'ตั้งรหัสผ่านใหม่',
    ignore: 'ถ้าคุณไม่ได้ขอ ไม่ต้องทำอะไร รหัสผ่านเดิมยังใช้ได้ตามปกติ',
  },
  en: {
    subject: 'Reset your password — TrackTrade',
    greeting: (name) => `Hi ${name}`,
    body: 'We received a request to reset the password of your TrackTrade account. This link works once and expires in 1 hour.',
    action: 'Reset password',
    ignore: "If you didn't ask for this, you can ignore this email — your password stays the same.",
  },
}

const escapeHtml = (value: string) =>
  value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)

export function resetPasswordMail(to: string, name: string, locale: string | undefined, url: string): Mail {
  const copy = RESET_COPY[locale === 'en' ? 'en' : 'th']
  const safeName = escapeHtml(name)
  const safeUrl = escapeHtml(url)
  return {
    to,
    subject: copy.subject,
    text: `${copy.greeting(name)}\n\n${copy.body}\n\n${copy.action}: ${url}\n\n${copy.ignore}\n`,
    // Email clients ignore CSS variables, so light-theme token values are inlined: ink, ink-muted, brand-600 fill + on-brand text.
    html: `<!doctype html><html><body style="font-family:Inter,Anuphan,Arial,sans-serif;line-height:1.6;color:#27221F">
<p>${copy.greeting(safeName)}</p>
<p>${copy.body}</p>
<p><a href="${safeUrl}" style="display:inline-block;padding:10px 16px;border-radius:10px;background:#D5B6B9;color:#2B2124;text-decoration:none;font-weight:600">${copy.action}</a></p>
<p style="font-size:13px;color:#6A6260">${copy.ignore}</p>
<p style="font-size:12px;color:#6A6260;word-break:break-all">${safeUrl}</p>
</body></html>`,
  }
}
