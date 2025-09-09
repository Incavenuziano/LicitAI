import React from 'react';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], weight: ['400','700'] });

const LogoBranca = (props: React.HTMLAttributes<HTMLDivElement>) => {
  // Este código foi convertido do arquivo logo_branca.html
  return (
    <div {...props}>
      <div style={{ width: 309, height: 307, position: 'relative' }}>
        <svg width="267" height="190" viewBox="852 2092 267 190" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 23, top: 0 }}>
          <path d="M1094.43603515625,2092L952.3919677734375,2236L877.6319580078125,2167L852,2192L952.3919677734375,2282L1119,2116L1094.43603515625,2092" fill="#ffffff"></path>
        </svg>
        <svg width="25" height="154" viewBox="1094 2130 25 154" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 265, top: 38 }}>
          <path d="M1119,2130L1094,2154.579833984375L1094,2284L1119,2284L1119,2130" fill="#6fd2e4"></path>
        </svg>
        <svg width="25" height="117" viewBox="1058 2166 25 117" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 229, top: 74 }}>
          <path d="M1082.468017578125,2166L1058,2191L1058.531982421875,2283L1083,2283L1082.468017578125,2166" fill="#6fd2e4"></path>
        </svg>
        <svg width="25" height="81" viewBox="1021 2203 25 81" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 192, top: 111 }}>
          <path d="M1046,2203L1021,2228.5L1021,2284L1046,2284L1046,2203" fill="#6fd2e4"></path>
        </svg>
        <svg width="25" height="46" viewBox="985 2239 25 46" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 156, top: 147 }}>
          <path d="M1010,2239L985,2264.27490234375L985,2285L1010,2285L1010,2239" fill="#6fd2e4"></path>
        </svg>
        <svg width="25" height="46" viewBox="891 2237 25 46" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: 'absolute', left: 62, top: 145 }}>
          <path d="M891,2237L916,2262.27490234375L916,2283L891,2283L891,2237" fill="#6fd2e4"></path>
        </svg>
        <div style={{ position: 'absolute', left: 0, top: 179, height: 128 }}>
          <p style={{ margin: 0 }}>
            <span className={inter.className} style={{ color: 'rgba(255, 255, 255, 1)', fontSize: 106 }}>Licit</span>
            <span className={inter.className} style={{ color: 'rgba(111, 210, 228, 1)', fontSize: 106 }}>AI</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LogoBranca;
