// 版本号唯一来源: frontend/package.json (由 packaging/inject_version.py 与 VERSION 同步), 构建时经 vite define 注入。
declare const __APP_VERSION__: string;
export const APP_VERSION: string = __APP_VERSION__;
