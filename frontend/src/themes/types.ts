export interface ThemeColors {
  bg: {
    base: string;
    surface: string;
    raised: string;
    overlay: string;
  };
  text: {
    primary: string;
    secondary: string;
    muted: string;
    inverse: string;
  };
  brand: {
    primary: string;
    primaryHover: string;
    secondary: string;
    accent: string;
  };
  semantic: {
    success: string;
    warning: string;
    error: string;
    info: string;
  };
  border: {
    default: string;
    strong: string;
    subtle: string;
  };
}

export interface ThemeTypography {
  heading: string;
  body: string;
  mono: string;
  editor: {
    fontFamily: string;
    fontSize: string;
    lineHeight: string;
    letterSpacing: string;
  };
}

export interface ThemeSpacing {
  radius: {
    sm: string;
    md: string;
    lg: string;
  };
}

export interface ThemeEffects {
  shadow: string;
  glass: string;
  glow: string;
}

export interface Theme {
  id: string;
  name: string;
  description: string;
  colors: ThemeColors;
  typography: ThemeTypography;
  spacing: ThemeSpacing;
  effects: ThemeEffects;
}
