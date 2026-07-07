import { Resvg } from "@resvg/resvg-js";
import pngToIco from "png-to-ico";
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const appRoot = process.cwd();
const sourceLogo = resolve(appRoot, "docs", "public", "logo.svg");
const publicLogo = resolve(appRoot, "public", "logo.svg");
const assetsRoot = resolve(appRoot, "desktop-assets");
const logoSvg = resolve(assetsRoot, "logo.svg");
const logoPng = resolve(assetsRoot, "logo.png");
const logoIco = resolve(assetsRoot, "logo.ico");

if (!existsSync(sourceLogo)) {
  throw new Error(`Logo source not found: ${sourceLogo}`);
}

mkdirSync(resolve(appRoot, "public"), { recursive: true });
mkdirSync(assetsRoot, { recursive: true });
cpSync(sourceLogo, publicLogo);
cpSync(sourceLogo, logoSvg);

const svg = readFileSync(sourceLogo);

// 生成一个较大的 PNG 供应用内使用
const largeResvg = new Resvg(svg, {
  fitTo: { mode: "width", value: 512 },
  background: "rgba(0, 0, 0, 0)",
});
const largePng = largeResvg.render().asPng();
writeFileSync(logoPng, largePng);

// 生成多尺寸 PNG 并合成标准 Windows ico，避免单张大图导致图标过大/加载失败。
const iconSizes = [16, 32, 48, 64, 128, 256];
const iconPngs = iconSizes.map((size) => {
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: size },
    background: "rgba(0, 0, 0, 0)",
  });
  return resvg.render().asPng();
});
writeFileSync(logoIco, await pngToIco(iconPngs));

console.log(`Desktop icons generated at ${assetsRoot}`);
