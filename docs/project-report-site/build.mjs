import fs from 'node:fs';
const report=JSON.parse(fs.readFileSync(new URL('./report-data.json',import.meta.url),'utf8'));
if(!Number.isInteger(report.tests)||report.tests<1||report.roadmap.length!==10)throw Error('Invalid verification or roadmap');
if(new Set(report.roadmap.map(r=>r.id)).size!==report.roadmap.length)throw Error('Duplicate roadmap id');
for(const item of report.roadmap){
  if(!['implemented','partial','planned'].includes(item.status)||!item.remaining||!Array.isArray(item.built))throw Error('Incomplete roadmap item');
}
const serialized=JSON.stringify(report,null,2).replace(/</g,'\\u003c');
fs.writeFileSync(new URL('./dist/report-data.js',import.meta.url),'window.REPORT = '+serialized+';\n');
const html=fs.readFileSync(new URL('./dist/index.html',import.meta.url),'utf8');
for(const file of ['style.css','app.js','report-data.js']){
 if(!fs.existsSync(new URL('./dist/'+file,import.meta.url))||!html.includes(file))throw Error('Missing asset '+file);
}
console.log('Report content and static assets verified. '+report.tests+' recorded tests; '+report.roadmap.length+' roadmap workstreams.');
