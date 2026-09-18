const { defineConfig } = require('@playwright/test');
const path = require('path');

module.exports = defineConfig({
  testDir: path.join(__dirname),
  testMatch: 'kiosk.spec.js',
  timeout: 30000,
  use: {
    headless: true,
  },
});
