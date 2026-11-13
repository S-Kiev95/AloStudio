import type { ReactNode } from "react";

import { type IconComponent, Instagram, WhatsApp } from "@/components/ui/brand-icons";
import { cn } from "@/lib/utils";

/** The app's own icon set, for the sidebar and Inicio: a rounded line with a
 *  soft fill behind it. Everything follows the text color, so the sidebar's
 *  neon styles keep applying. */
function appIcon(fill: ReactNode, line: ReactNode): IconComponent {
  return function AppIcon(props) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.7}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...props}
      >
        <g fill="currentColor" fillOpacity={0.2} stroke="none">
          {fill}
        </g>
        {line}
      </svg>
    );
  };
}

const HOME = "M4 11.2 12 4l8 7.2V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z";
export const HomeIcon = appIcon(
  <path d={HOME} />,
  <>
    <path d={HOME} />
    <path d="M9.75 20.5V15.5a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1v5" />
  </>,
);

export const CalendarIcon = appIcon(
  <path d="M6.5 5h11a3 3 0 0 1 3 3v2h-17V8a3 3 0 0 1 3-3z" />,
  <>
    <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
    <path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01" strokeWidth={2.2} />
  </>,
);

const STAR =
  "M11 4.5l1.8 5a3 3 0 0 0 1.8 1.8l5 1.7-5 1.7a3 3 0 0 0-1.8 1.8l-1.8 5-1.8-5a3 3 0 0 0-1.8-1.8l-5-1.7 5-1.7a3 3 0 0 0 1.8-1.8z";
export const AgentIcon = appIcon(
  <path d={STAR} />,
  <>
    <path d={STAR} />
    <path d="M19 3v4M17 5h4" />
  </>,
);

export const StatsIcon = appIcon(
  <path d="M7.5 15.5l3.5-4 3 2.5 5-6.5V17H7.5z" />,
  <>
    <path d="M4 4v14a2 2 0 0 0 2 2h14" />
    <path d="M7.5 15.5l3.5-4 3 2.5 5-6.5" />
  </>,
);

export const MediaIcon = appIcon(
  <path d="M3.5 16.5l5-4.5 3.5 3 3.5-4 5 5.5v.5a3 3 0 0 1-3 3h-11a3 3 0 0 1-3-3z" />,
  <>
    <rect x="3.5" y="4.5" width="17" height="15.5" rx="3" />
    <circle cx="8.5" cy="9" r="1.5" />
    <path d="M3.5 16.5l5-4.5 3.5 3 3.5-4 5 5.5" />
  </>,
);

export const InboxIcon = appIcon(
  <path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5V17a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 17z" />,
  <>
    <path d="M3.5 13.5l2.6-7.2A2 2 0 0 1 8 5h8a2 2 0 0 1 1.9 1.3l2.6 7.2V17a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 17z" />
    <path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5" />
  </>,
);

export const PeopleIcon = appIcon(
  <>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 19.5c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5z" />
  </>,
  <>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 19.5c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5" />
    <path d="M16 4.8a3.3 3.3 0 0 1 0 6.4M17.5 14.4c1.9.6 3.1 2.4 3.5 5.1" />
  </>,
);

export const BookIcon = appIcon(
  <path d="M12 7c-1.6-1.6-4-2.4-8.5-2.5V18c4.5.1 6.9.9 8.5 2.5z" />,
  <>
    <path d="M12 7c-1.6-1.6-4-2.4-8.5-2.5V18c4.5.1 6.9.9 8.5 2.5 1.6-1.6 4-2.4 8.5-2.5V4.5C16 4.6 13.6 5.4 12 7z" />
    <path d="M12 7v13.5" />
  </>,
);

const HORN = "M4 10.2v3.6a1 1 0 0 0 1 1h2.5L18 19.5v-15L7.5 9.2H5a1 1 0 0 0-1 1z";
export const MegaphoneIcon = appIcon(
  <path d={HORN} />,
  <>
    <path d={HORN} />
    <path d="M21 10v4M8 15l1.1 4.3a1 1 0 0 0 1 .7h.9a1 1 0 0 0 1-1.2l-.7-3" />
  </>,
);

export const BarsIcon = appIcon(
  <>
    <rect x="4" y="12.5" width="4" height="7.5" rx="1.2" />
    <rect x="10" y="4" width="4" height="16" rx="1.2" />
    <rect x="16" y="8.5" width="4" height="11.5" rx="1.2" />
  </>,
  <>
    <rect x="4" y="12.5" width="4" height="7.5" rx="1.2" />
    <rect x="10" y="4" width="4" height="16" rx="1.2" />
    <rect x="16" y="8.5" width="4" height="11.5" rx="1.2" />
  </>,
);

export const ClockIcon = appIcon(
  <circle cx="12" cy="13" r="8" />,
  <>
    <circle cx="12" cy="13" r="8" />
    <path d="M12 8.5V13l3 2M5 3.5 2.5 6M19 3.5 21.5 6" />
  </>,
);

export const UnassignedIcon = appIcon(
  <>
    <circle cx="10" cy="8" r="3.5" />
    <path d="M3.5 20c.6-3.6 3.2-5.8 6.5-5.8 1.4 0 2.7.4 3.8 1.1V20z" />
  </>,
  <>
    <circle cx="10" cy="8" r="3.5" />
    <path d="M3.5 20c.6-3.6 3.2-5.8 6.5-5.8 1.4 0 2.7.4 3.8 1.1" />
    <path d="M16.5 15.5l4 4M20.5 15.5l-4 4" />
  </>,
);

export const HourglassIcon = appIcon(
  <path d="M8 20.5v-3.2c0-1.4.7-2.7 1.9-3.5L12 12l2.1 1.8c1.2.8 1.9 2.1 1.9 3.5v3.2z" />,
  <>
    <path d="M6.5 3.5h11M6.5 20.5h11" />
    <path d="M8 3.5v3.2c0 1.4.7 2.7 1.9 3.5L12 12l2.1-1.8A4.2 4.2 0 0 0 16 6.7V3.5" />
    <path d="M8 20.5v-3.2c0-1.4.7-2.7 1.9-3.5L12 12l2.1 1.8c1.2.8 1.9 2.1 1.9 3.5v3.2" />
  </>,
);

const BUBBLE =
  "M3.5 6.5A2.5 2.5 0 0 1 6 4h8a2.5 2.5 0 0 1 2.5 2.5v5A2.5 2.5 0 0 1 14 14H8.5L5 17v-3.1a2.5 2.5 0 0 1-1.5-2.4z";
export const MessagesIcon = appIcon(
  <path d={BUBBLE} />,
  <>
    <path d={BUBBLE} />
    <path d="M20 8.5a2 2 0 0 1 .5 1.5v5a2.5 2.5 0 0 1-1.5 2.4V20l-3.5-3H11" />
  </>,
);

/** Instagram's own logo, in the text color so the sidebar's neon applies, and
 *  a little smaller: it fills its whole box, unlike the rest of the set. */
export const InstagramNavIcon: IconComponent = ({ className, ...props }) => (
  <Instagram mono className={cn("scale-[0.85]", className)} {...props} />
);

/** WhatsApp's logo, same treatment as Instagram's. */
export const WhatsappNavIcon: IconComponent = ({ className, ...props }) => (
  <WhatsApp mono className={cn("scale-[0.85]", className)} {...props} />
);

const SIDEBAR_PANE =
  "M6.5 4.5h3v15h-3a3 3 0 0 1-3-3v-9a3 3 0 0 1 3-3z";

export const SidebarCollapseIcon = appIcon(
  <path d={SIDEBAR_PANE} />,
  <>
    <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
    <path d="M9.5 4.5v15" />
    <path d="M16 9.5 13.5 12l2.5 2.5" />
  </>,
);

export const SidebarExpandIcon = appIcon(
  <path d={SIDEBAR_PANE} />,
  <>
    <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
    <path d="M9.5 4.5v15" />
    <path d="M13.5 9.5 16 12l-2.5 2.5" />
  </>,
);

