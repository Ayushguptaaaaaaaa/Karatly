import { createTheme, type MantineColorsTuple } from "@mantine/core";

const gold: MantineColorsTuple = [
  "#fbf6e9", "#f4e9c9", "#ead7a0", "#dfc373", "#d5b24e",
  "#cfa636", "#c99e2a", "#b0891f", "#9d7a18", "#86670e",
];

const ink: MantineColorsTuple = [
  "#f7f5f0", "#e9e4d8", "#d4cdbd", "#b5ad9b", "#8f887a",
  "#6b665e", "#4e4a43", "#38352f", "#2c2a26", "#1f1d1a",
];

export const theme = createTheme({
  primaryColor: "gold",
  primaryShade: { light: 7, dark: 5 },
  colors: { gold, ink },
  fontFamily: '"Inter Variable", Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
  fontFamilyMonospace: 'ui-monospace, "JetBrains Mono", Consolas, monospace',
  headings: {
    fontFamily: '"Playfair Display", Georgia, serif',
    fontWeight: "600",
  },
  defaultRadius: "md",
  radius: { xs: "4px", sm: "8px", md: "12px", lg: "16px", xl: "20px" },
  cursorType: "pointer",
  autoContrast: true,
  components: {
    Card: { defaultProps: { radius: "md", withBorder: true, padding: "lg" } },
    Paper: { defaultProps: { radius: "md" } },
    Button: { defaultProps: { radius: "md" } },
    Badge: { defaultProps: { radius: "xl", variant: "light" } },
    Modal: { defaultProps: { radius: "lg", centered: true, overlayProps: { backgroundOpacity: 0.45, blur: 3 } } },
    Drawer: { defaultProps: { overlayProps: { backgroundOpacity: 0.4, blur: 2 } } },
    Tooltip: { defaultProps: { withArrow: true, openDelay: 250 } },
    TextInput: { defaultProps: { radius: "md" } },
    NumberInput: { defaultProps: { radius: "md", thousandSeparator: ",", thousandsGroupStyle: "lakh" } },
  },
});
