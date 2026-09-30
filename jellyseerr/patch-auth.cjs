const fs = require('fs');

for (const file of ['dist/api/jellyfin.js', 'dist/routes/auth.js', 'dist/routes/avatarproxy.js']) {
  const p = '/app/' + file;
  if (fs.existsSync(p)) {
    let s = fs.readFileSync(p, 'utf8');
    s = s.replace(/('X-Emby-Authorization':\s*(.*)),$/gm, "$1,\n'Authorization': $2,");
    fs.writeFileSync(p, s);
  }
}
