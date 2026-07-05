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
const resvg = new Resvg(svg, {
  fitTo: {
    mode: "width",
    value: 512,
  },
  background: "rgba(0, 0, 0, 0)",
});
const png = resvg.render().asPng();

writeFileSync(logoPng, png);
writeFileSync(logoIco, await pngToIco([png]));

console.log(`Desktop icons generated at ${assetsRoot}`);
