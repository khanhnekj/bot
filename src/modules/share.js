import fs from "node:fs";
import path from "node:path";
import archiver from "archiver";

export const name = "share";
export const description = "File Manager";

const sessions = new Map();

export const commands = {
share: async (ctx)=>{

const { api, threadId, threadType, senderId, args, adminIds } = ctx;

if(!adminIds.includes(String(senderId))){
return api.sendMessage(
{msg:"⚠️ Admin đâu?"},
threadId,
threadType
);
}

let dir = args.join(" ").trim();

if(!dir) dir = process.cwd();
else if(!path.isAbsolute(dir))
dir = path.resolve(process.cwd(),dir);

if(!fs.existsSync(dir)){
return api.sendMessage(
{msg:"⚠️ Đéo tồn tại"},
threadId,
threadType
);
}

const stat = fs.statSync(dir);

if(stat.isFile()){
return sendFile(api,threadId,threadType,dir);
}

return listDir(api,threadId,threadType,senderId,dir);

}
};

async function listDir(api,threadId,threadType,senderId,dir){

const files = fs.readdirSync(dir);

const items = files.map(f=>{

const fp = path.join(dir,f);
const st = fs.statSync(fp);

return {
name:f,
path:fp,
isDir:st.isDirectory(),
mtime:st.mtimeMs
};

});

items.sort((a,b)=>{
if(a.isDir!==b.isDir) return b.isDir-a.isDir;
return b.mtime-a.mtime;
});

const show = items.slice(0,100);

let msg = `📂 [ THƯ MỤC: ${path.basename(dir).toUpperCase() || "ROOT"} ]\n`;
msg += `─────────────────\n`;
msg += `📁 .. (Thư mục cha)\n`;

show.forEach((it,i)=>{
msg += `${i+1}. ${it.isDir?"📁":"📄"} ${it.name}\n`;
});

msg += `─────────────────\n`;
msg += `💡 STT → mở/gửi\n`;
msg += `💡 zip STT  → nén gửi\n`;
msg += `💡 + filename → tạo file\n`;
msg += `💡 ++ folder → tạo folder\n`;
msg += `💡 - STT → xóa\n`;
msg += `💡 up → quay lại\n\n`;
msg += `📌 Đường dẫn:\n${dir}`;

await api.sendMessage({msg},threadId,threadType);

sessions.set(`${threadId}-${senderId}`,{
path:dir,
items:show,
pendingZip:null
});

}

async function sendFile(api,threadId,threadType,file){

const name = path.basename(file);
const size = fs.statSync(file).size/1024/1024;

if(size>100){
return api.sendMessage(
{msg:`⚠️ File ${size.toFixed(2)}MB >100MB`},
threadId,
threadType
);
}

await api.sendMessage(
{
msg:`📄 ${name}`,
attachments:[file]
},
threadId,
threadType
);

}

async function zipFiles(api,threadId,threadType,files,dir){

const zipName = `share_${Date.now()}.zip`;
const zipPath = path.join(dir,zipName);

const output = fs.createWriteStream(zipPath);
const archive = archiver("zip",{zlib:{level:9}});

archive.pipe(output);

files.forEach(f=>{
const name = path.basename(f);

if(fs.statSync(f).isDirectory())
archive.directory(f,name);
else
archive.file(f,{name});
});

await archive.finalize();

output.on("close",async()=>{

await api.sendMessage(
{
msg:`📦 ${zipName}`,
attachments:[zipPath]
},
threadId,
threadType
);

fs.unlinkSync(zipPath);

});

}

export async function handle(ctx){

const { api, threadId, threadType, senderId, content } = ctx;

const key = `${threadId}-${senderId}`;
const session = sessions.get(key);

if(!session) return false;

const input = content.trim().toLowerCase();

/* xác nhận zip */

if(session.pendingZip){

if(input==="y"){

await zipFiles(
api,
threadId,
threadType,
session.pendingZip,
session.path
);

session.pendingZip=null;

return true;
}

if(input==="n"){

session.pendingZip=null;

api.sendMessage(
{msg:"❌ Đã hủy zip"},
threadId,
threadType
);

return true;
}

}

/* quay lại */

if(input==="up"||input==="0"){

const parent = path.dirname(session.path);

return listDir(api,threadId,threadType,senderId,parent);

}

/* tạo folder */

if(input.startsWith("++")){

let name = input.slice(2).trim();

const fp = path.join(session.path,name);

fs.mkdirSync(fp,{recursive:true});

api.sendMessage(
{msg:`📁 Đã tạo folder ${name}`},
threadId,
threadType
);

return listDir(api,threadId,threadType,senderId,session.path);

}

/* tạo file */

if(input.startsWith("+")){

let name = input.slice(1).trim();

if(!name.includes(".")) name+=".js";

const fp = path.join(session.path,name);

fs.writeFileSync(fp,"");

api.sendMessage(
{msg:`📄 Đã tạo file ${name}`},
threadId,
threadType
);

return listDir(api,threadId,threadType,senderId,session.path);

}

/* xóa */

if(input.startsWith("-")){

const nums = input
.slice(1)
.trim()
.split(/\s+/)
.map(n=>parseInt(n));

nums.forEach(n=>{

const it = session.items[n-1];

if(!it) return;

if(fs.statSync(it.path).isDirectory())
fs.rmSync(it.path,{recursive:true,force:true});
else
fs.unlinkSync(it.path);

});

api.sendMessage(
{msg:"Đã xóa rồi em"},
threadId,
threadType
);

return listDir(api,threadId,threadType,senderId,session.path);

}

/* zip có xác nhận */

if(input.startsWith("zip")){

const nums = input
.slice(3)
.trim()
.split(/\s+/)
.map(n=>parseInt(n));

const files = nums
.map(n=>session.items[n-1]?.path)
.filter(Boolean);

session.pendingZip = files;

api.sendMessage(
{msg:"⚠️ Xác nhận zip? (y/n)"},
threadId,
threadType
);

return true;

}

/* auto zip */

if(/^[0-9\s]+$/.test(input) && input.includes(" ")){

const nums = input
.split(/\s+/)
.map(n=>parseInt(n));

const files = nums
.map(n=>session.items[n-1]?.path)
.filter(Boolean);

await zipFiles(
api,
threadId,
threadType,
files,
session.path
);

return true;

}

/* mở hoặc gửi */

const n = parseInt(input);

if(!isNaN(n) && n>0 && n<=session.items.length){

const it = session.items[n-1];

if(it.isDir)
return listDir(api,threadId,threadType,senderId,it.path);
else
return sendFile(api,threadId,threadType,it.path);

}

return false;

}