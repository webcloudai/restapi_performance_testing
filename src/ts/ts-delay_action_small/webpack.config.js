const path = require('path');
const nodeExternals = require('webpack-node-externals');

module.exports = {
  entry: './index.ts', // Entry point of your Lambda function
  target: 'node', // Target Node.js environment
  mode: 'production', // Ensure the code is optimized
  externals: [
    nodeExternals( { allowlist: ['uuid'] } )
  ], // Exclude node_modules from the bundle
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: 'ts-loader', // Use ts-loader to handle TypeScript files
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: ['.ts', '.js'], // Resolve both TypeScript and JavaScript files
  },
  output: {
    filename: 'index.js', // Output file
    path: path.resolve(__dirname, 'zip'), // Output directory
    libraryTarget: 'commonjs2', // Suitable for Node.js modules
  },
  optimization: {
    // Minimize the bundle size
    minimize: true,
  },
};