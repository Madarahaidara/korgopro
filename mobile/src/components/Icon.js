// ============================================================================
// Composant d'icône SVG pour mobile — strictement calqué sur web/src/components/Icon.jsx
// ============================================================================
import React from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

export default function Icon({ name, size = 20, color = 'currentColor', strokeWidth = 2, style }) {
  const c = color;
  const sw = strokeWidth;

  const renderContent = () => {
    switch (name) {
      case 'dashboard':
        return (
          <>
            <Rect x="3" y="3" width="7" height="9" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Rect x="14" y="3" width="7" height="5" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Rect x="14" y="12" width="7" height="9" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Rect x="3" y="16" width="7" height="5" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'sale':
        return (
          <>
            <Circle cx="9" cy="20" r="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Circle cx="17" cy="20" r="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M3 3h2l2.4 12.2a1 1 0 0 0 1 .8h8.9a1 1 0 0 0 1-.8L21 7H6" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'stock':
        return (
          <>
            <Path d="M21 8v8a2 2 0 0 1-1 1.73l-7 4a2 2 0 0 1-2 0l-7-4A2 2 0 0 1 3 16V8a2 2 0 0 1 1-1.73l7-4a2 2 0 0 1 2 0l7 4A2 2 0 0 1 21 8z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M3.3 7l8.7 5 8.7-5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M12 22V12" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'receipt':
        return (
          <>
            <Path d="M5 3h14v18l-2.33-1.5L14.33 21 12 19.5 9.67 21l-2.34-1.5L5 21z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M9 7.5h6M9 11h6M9 14.5h4" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'user':
        return (
          <>
            <Circle cx="12" cy="8" r="4" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'check':
        return <Path d="M20 6L9 17l-5-5" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'cancel':
        return <Path d="M18 6L6 18M6 6l12 12" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'cash':
        return (
          <>
            <Rect x="2.5" y="6" width="19" height="12" rx="2" stroke={c} strokeWidth={sw} fill="none" />
            <Circle cx="12" cy="12" r="2.8" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M6 9.5h.01M18 14.5h.01" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'search':
        return (
          <>
            <Circle cx="11" cy="11" r="7" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M21 21l-4.3-4.3" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'refresh':
        return <Path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'alert':
        return (
          <>
            <Path d="M10.3 3.9L1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
            <Path d="M12 9v4M12 17h.01" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'chevronDown':
        return <Path d="M6 9l6 6 6-6" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'document':
        return (
          <>
            <Path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M14 3v6h6" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M9 13h6M9 17h6" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'admin':
        return (
          <>
            <Path d="M12 3l8 3v5c0 4.9-3.4 8.4-8 10-4.6-1.6-8-5.1-8-10V6z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M9 12l2 2 4-4" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </>
        );
      case 'settings':
        return (
          <>
            <Circle cx="12" cy="12" r="3.2" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M12 2.5v2.6M12 18.9v2.6M2.5 12h2.6M18.9 12h2.6M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'treasury':
        return (
          <>
            <Path d="M3 9.5L12 4l9 5.5" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
            <Path d="M4 10v9M20 10v9M9.5 10v9M14.5 10v9" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
            <Path d="M2.5 21h19" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'lock':
        return (
          <>
            <Rect x="5" y="11" width="14" height="10" rx="2" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M8 11V7a4 4 0 0 1 8 0v4" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'monitor':
        return (
          <>
            <Rect x="3" y="4" width="18" height="12" rx="2" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M8 20h8M12 16v4" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'globe':
        return (
          <>
            <Circle cx="12" cy="12" r="9" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'hardDrive':
        return (
          <>
            <Rect x="3" y="5" width="18" height="6" rx="2" stroke={c} strokeWidth={sw} fill="none" />
            <Rect x="3" y="13" width="18" height="6" rx="2" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M7 8h.01M7 16h.01" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'clock':
        return (
          <>
            <Circle cx="12" cy="12" r="9" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M12 7v5l3.5 2" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </>
        );
      case 'activity':
        return <Path d="M22 12h-4l-3 8-6-16-3 8H2" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'building':
        return (
          <>
            <Rect x="4" y="3" width="16" height="18" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
            <Path d="M10 21v-3h4v3" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'checkCircle':
        return (
          <>
            <Circle cx="12" cy="12" r="9" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M8.5 12.5l2.5 2.5 4.5-5" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </>
        );
      case 'zap':
        return <Path d="M13 2L4.5 13.5H11l-1 8.5L18.5 10H12z" stroke={c} strokeWidth={sw} fill="none" strokeLinejoin="round" />;
      case 'users':
        return (
          <>
            <Circle cx="9" cy="8" r="3.5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
            <Path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M17.5 14.7c2.4.7 4 2.4 4 5.3" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'list':
        return <Path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />;
      case 'chart':
        return <Path d="M4 20V10M10 20V4M16 20v-8M21 20H3" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'wallet':
        return (
          <>
            <Path d="M21 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M21 8h-6a3 3 0 0 0 0 8h6v-8z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M16.5 12h.01" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'phone':
        return (
          <>
            <Rect x="6" y="2.5" width="12" height="19" rx="2.5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M10.5 18.5h3" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'broom':
        return <Path d="M19 3l-8 8M12 11l-2 2c-3 0-6 2-7 8 6-1 8-4 8-7l2-2zM7 15c1 1.5 1.5 2 3 3" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'export':
        return <Path d="M12 15V4M8 8l4-4 4 4M4 20h16" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'import':
        return <Path d="M12 4v11M8 12l4 4 4-4M4 20h16" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'add':
        return <Path d="M12 5v14M5 12h14" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />;
      case 'edit':
        return <Path d="M17 3l4 4L8.5 19.5 4 20l.5-4.5z" stroke={c} strokeWidth={sw} fill="none" strokeLinejoin="round" />;
      case 'delete':
        return (
          <>
            <Path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
            <Path d="M6 6l1 15h10l1-15" stroke={c} strokeWidth={sw} fill="none" strokeLinejoin="round" />
            <Path d="M10 11v6M14 11v6" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" />
          </>
        );
      case 'save':
        return (
          <>
            <Path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" stroke={c} strokeWidth={sw} fill="none" strokeLinejoin="round" />
            <Path d="M17 21v-8H7v8M7 3v5h8" stroke={c} strokeWidth={sw} fill="none" strokeLinejoin="round" />
          </>
        );
      case 'print':
        return (
          <>
            <Path d="M6 9V3h12v6" stroke={c} strokeWidth={sw} fill="none" />
            <Rect x="4" y="9" width="16" height="8" rx="1.5" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M7 17h10v4H7z" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'arrowRight':
        return <Path d="M5 12h14M13 5l7 7-7 7" stroke={c} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
      case 'store':
        return (
          <>
            <Path d="M3 9l9-6 9 6v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9z" stroke={c} strokeWidth={sw} fill="none" />
            <Path d="M9 21V12h6v9" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      case 'menu':
        return (
          <>
            <Path d="M4 6h16M4 12h16M4 18h16" stroke={c} strokeWidth={sw} fill="none" />
          </>
        );
      default:
        return null;
    }
  };

  return (
    <Svg viewBox="0 0 24 24" width={size} height={size} style={style}>
      {renderContent()}
    </Svg>
  );
}
