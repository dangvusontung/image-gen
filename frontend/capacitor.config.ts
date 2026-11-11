import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.characterstudio.app',
  appName: 'Character Studio',
  webDir: 'dist',
  server: { androidScheme: 'http', cleartext: true },
  plugins: { CapacitorHttp: { enabled: true } },
}
export default config
