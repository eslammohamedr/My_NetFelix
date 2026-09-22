# Keep the runtime and source pinned to the same Jellyseerr release.
FROM fallenbagel/jellyseerr@sha256:4538137bc5af902dece165f2bf73776d9cf4eafb6dd714670724af8f3eb77764 AS build
ADD --checksum=sha256:d0444cecd385452e452954b13b8a0e2b9b299fbef0cecc70c44ad089d8d84b78 https://codeload.github.com/Fallenbagel/jellyseerr/tar.gz/refs/tags/v2.7.3 /tmp/source.tar.gz
RUN tar -xzf /tmp/source.tar.gz -C /app --strip-components=1
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS=--max-old-space-size=2048 CYPRESS_INSTALL_BINARY=0
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY WatchNowButton.tsx src/components/WatchNowButton/index.tsx
COPY patch.cjs /tmp/netfelix-patch.cjs
RUN node /tmp/netfelix-patch.cjs && pnpm exec prettier --write src/components/WatchNowButton/index.tsx src/components/MovieDetails/index.tsx src/components/TvDetails/index.tsx next.config.js
RUN pnpm build:next

FROM fallenbagel/jellyseerr@sha256:4538137bc5af902dece165f2bf73776d9cf4eafb6dd714670724af8f3eb77764
COPY --from=build /app/.next /app/.next
COPY --from=build /app/next.config.js /app/next.config.js
# Jellyfin 12+ requires standard Authorization header alongside or instead of legacy X-Emby-Authorization
RUN node -e "for (const file of ['dist/api/jellyfin.js', 'dist/routes/auth.js', 'dist/routes/avatarproxy.js']) { const p = '/app/' + file; if (require('fs').existsSync(p)) { let s = require('fs').readFileSync(p, 'utf8'); s = s.replace(/'X-Emby-Authorization': (.*?),/g, \"'X-Emby-Authorization': \$1,\\n'Authorization': \$1,\"); require('fs').writeFileSync(p, s); } }"
# Mark build as local to disable upstream update banners in custom container
RUN echo '{"commitTag": "local"}' > /app/committag.json

