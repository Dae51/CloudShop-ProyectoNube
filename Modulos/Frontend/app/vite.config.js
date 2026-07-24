import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js"
  },
  build: {
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          cognito: [
            "amazon-cognito-identity-js",
            "@aws-sdk/client-cognito-identity",
            "@aws-sdk/credential-provider-cognito-identity"
          ],
          signing: [
            "@aws-crypto/sha256-js",
            "@aws-sdk/protocol-http",
            "@aws-sdk/signature-v4"
          ]
        }
      }
    }
  }
});
