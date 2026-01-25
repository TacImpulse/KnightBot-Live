/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/knight/:path*', destination: 'http://127.0.0.1:8100/:path*' },
      { source: '/api/stt/:path*', destination: 'http://127.0.0.1:8070/:path*' },
      { source: '/api/tts/:path*', destination: 'http://127.0.0.1:8060/:path*' },
    ];
  },
};
