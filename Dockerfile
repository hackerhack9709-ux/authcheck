# PayCheck — one-container deploy (Railway / Render / Fly / any Docker host).
#
# The server is zero-dependency, so the image is just Node plus the static
# files. Secrets are passed as environment variables at run time; nothing is
# baked into the image.

FROM node:20-alpine

ENV NODE_ENV=production
WORKDIR /app

# Only the files the server actually reads. --chown so the unprivileged
# runtime user can read them regardless of the source file modes.
COPY --chown=node:node package.json ./
COPY --chown=node:node server/ ./server/
COPY --chown=node:node index.html styles.css app.js auth.js gateway.js icons.js share.js sw.js ./
COPY --chown=node:node manifest.webmanifest ./
COPY --chown=node:node vendor/ ./vendor/
COPY --chown=node:node icon-192.png icon-512.png icon-maskable-512.png ./

# Run as the built-in unprivileged user.
USER node

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server/razorpay-verify.js"]
