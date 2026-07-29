/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server for slim Cloud Run images.
  output: "standalone",
};

export default nextConfig;
