const { defineConfig } = require('@vue/cli-service')
const webpack = require('webpack')
const path = require('path')

module.exports = defineConfig({
  publicPath: process.env.NODE_ENV === 'production' ? './' : '/',
  transpileDependencies: [],

  chainWebpack: config => {
    config.resolve.alias.set('@', path.resolve(__dirname, 'src'))

    config.plugin('define').tap(args => {
      const pkg = require('./package.json')
      args[0]['process.env.VUE_APP_VERSION'] = JSON.stringify(pkg.version)
      return args
    })
  }
})
