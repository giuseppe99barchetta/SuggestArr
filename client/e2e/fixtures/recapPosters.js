// Offline portrait artwork for recap screenshots. These are fictional test titles.
export const titles = ['ORBIT', 'AFTERLIGHT', 'NIGHT SIGNAL', 'THE LAST HORIZON'];

export function posterFixture(index) {
  const palettes = [['#092236', '#0097aa', '#b8f2ef'], ['#2f1533', '#c66152', '#ffd6a1'], ['#101d31', '#526bcd', '#b9bcf7'], ['#30231b', '#98624a', '#f5d9a8']];
  const [dark, mid, light] = palettes[index];
  const scenery = index === 0
    ? `<circle cx="220" cy="240" r="102" fill="${light}"/><ellipse cx="220" cy="240" rx="170" ry="40" fill="none" stroke="${mid}" stroke-width="24" transform="rotate(-30 220 240)"/><circle cx="72" cy="128" r="4" fill="white"/><circle cx="322" cy="87" r="3" fill="white"/>`
    : index === 1
      ? `<circle cx="200" cy="210" r="116" fill="${light}"/><path d="M0 380 120 230 245 380 340 260 400 380V600H0Z" fill="${dark}"/><path d="M0 450 160 310 300 460 400 340V600H0Z" fill="${mid}"/>`
      : index === 2
        ? `<path d="M30 450V270h45v180h30V180h60v270h30V320h45v130h30V130h65v320h35V230h40v370H0Z" fill="${dark}"/><path d="m200 60 80 190H120Z" fill="${light}" opacity=".4"/><circle cx="200" cy="270" r="26" fill="${light}"/>`
        : `<circle cx="280" cy="190" r="100" fill="${light}"/><path d="M0 400 125 210 240 390 315 285 400 425V600H0Z" fill="${mid}"/><path d="M0 475 155 330 320 500 400 400V600H0Z" fill="${dark}"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 400 600"><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="${dark}"/><stop offset="1" stop-color="${mid}"/></linearGradient></defs><rect width="400" height="600" fill="url(#sky)"/>${scenery}<text x="200" y="72" text-anchor="middle" fill="${light}" font-family="sans-serif" font-size="12" letter-spacing="5">A SUGGESTARR DISCOVERY</text><text x="200" y="520" text-anchor="middle" fill="white" font-family="sans-serif" font-weight="bold" font-size="${index === 3 ? 23 : 34}" letter-spacing="3">${titles[index]}</text><text x="200" y="552" text-anchor="middle" fill="${light}" font-family="sans-serif" font-size="10" letter-spacing="3">YOUR NEXT FAVORITE</text></svg>`;
}
