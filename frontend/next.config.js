/** @type {import('next').NextConfig} */
const path = require("path");

const nextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
  webpack: (config, { isServer }) => {
    // Point any `import "cesium"` to the pre-built bundle
    // This avoids webpack trying to parse cesium source (which pulls in @zip.js/zip.js)
    config.resolve.alias.cesium = path.join(
      __dirname,
      "node_modules/cesium/Build/Cesium/Cesium.js"
    );

    // Also mark cesium as external on the server side
    if (isServer) {
      config.externals = config.externals || [];
      config.externals.push("cesium");
    }

    return config;
  },
};

module.exports = nextConfig;
