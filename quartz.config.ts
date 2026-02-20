import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

const config: QuartzConfig = {
  configuration: {
    pageTitle: "KaaS",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "ru-RU",
    baseUrl: "localhost",
    ignorePatterns: [
      "private",
      "templates",
      ".obsidian",
      ".git",
      "node_modules",
      "3-Resources/Templates",
      "3-Resources/Tools/Developer Tools/Cloud Services/GCP/Google Colaboratory.md",
    ],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Schibsted Grotesk",
        body: "Source Sans Pro",
        code: "IBM Plex Mono",
      },
      colors: {
        lightMode: {
          light: "#f7f3e9",
          lightgray: "#e2d9c5",
          gray: "#8f7f63",
          darkgray: "#594f3b",
          dark: "#2c261a",
          secondary: "#0f766e",
          tertiary: "#b45309",
          highlight: "rgba(15, 118, 110, 0.14)",
          textHighlight: "#fef3c7",
        },
        darkMode: {
          light: "#17140f",
          lightgray: "#2b2418",
          gray: "#a19377",
          darkgray: "#d8ccb1",
          dark: "#f4ecd8",
          secondary: "#5eead4",
          tertiary: "#f59e0b",
          highlight: "rgba(94, 234, 212, 0.16)",
          textHighlight: "#78350f",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: false,
        enableRSS: false,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
    ],
  },
}

export default config
