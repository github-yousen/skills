/**
 * 番茄小说收益接口加密模块
 * 由 VM 代码段提取的 get_a/get_A/get_res 加密函数
 *
 * 依赖：crypto-js, bignumber.js
 * 安装：在技能目录执行 npm install crypto-js bignumber.js
 *
 * 用法：
 *   const enc = require('./fanqie_encrypt');
 *   const o = enc.get_a();          // 生成随机密钥
 *   const u = enc.get_A(o);         // 生成 X-Muye-Encrypt-Key 请求头值
 *   const data = enc.get_res(key, o, ciphertext);  // 解密响应
 */
const fs = require("fs");
const path = require("path");

let CryptoJS, BigNumber;
try {
    CryptoJS = require("crypto-js");
    BigNumber = require("bignumber.js");
} catch (e) {
    throw new Error("缺少依赖，请在技能目录执行: npm install crypto-js bignumber.js\n" + e.message);
}

BigNumber.isBigNumber = BigNumber.isBigNumber || function (v) { return v && v._isBigNumber === true; };

// 设置全局环境
global.window = global;
global.self = global;

// 构建 CryptoJS 库对象
const g = {};
g.BigNumber = BigNumber;
g.AES = CryptoJS.AES;
g.SHA256 = CryptoJS.SHA256;
g.Utf8 = CryptoJS.enc.Utf8;
g.Hex = CryptoJS.enc.Hex;
global._$jsvmprt = null;

// 加载 VM 代码段
const vmCodePath = path.join(__dirname, "..", "references", "vm_code.js");
if (!fs.existsSync(vmCodePath)) {
    throw new Error("VM代码段不存在: " + vmCodePath + "\n请确保 references/vm_code.js 已生成");
}
const vmCode = fs.readFileSync(vmCodePath, "utf-8");

// 执行 VM 代码，填充 Q[1]
eval(vmCode);

if (typeof Q === "undefined" || !Q[1] || !Q[1].get_a) {
    throw new Error("VM执行失败，Q[1]未填充加密函数");
}

// 导出加密函数
module.exports = {
    get_a: Q[1].get_a,
    get_A: Q[1].get_A,
    get_res: Q[1].get_res,
};
