const fs = require('fs');
for (const [component, mediaType] of [['MovieDetails', 'movie'], ['TvDetails', 'tv']]) {
  const path = `src/components/${component}/index.tsx`;
  let source = fs.readFileSync(path, 'utf8');
  const marker = '          <div className="z-20">\n            <PlayButton links={mediaLinks} />';
  if (source.split(marker).length !== 2) throw new Error(`Unexpected upstream layout in ${path}`);
  source = "import WatchNowButton from '@app/components/WatchNowButton';\n" + source;
  source = source.replace(marker, `          <WatchNowButton mediaType="${mediaType}" tmdbId={data.id} media={data.mediaInfo} />\n${marker}`);
  fs.writeFileSync(path, source);
}
const path = 'next.config.js';
const config = fs.readFileSync(path, 'utf8');
if (!config.includes('  experimental: {')) throw new Error('Next config changed');
fs.writeFileSync(path, config.replace('  experimental: {', '  experimental: {\n    cpus: 1,'));
