"use client";

import { type ComponentType, type ReactNode, useId } from "react";

import { Instagram, WhatsApp } from "@/components/ui/brand-icons";
import { cn } from "@/lib/utils";

export type IconAnimate = "loop" | "hover" | "none";

export type AppIconProps = {
  className?: string;
  "aria-hidden"?: boolean | "true" | "false";
  animate?: IconAnimate;
};

export type AppIconComponent = ComponentType<AppIconProps>;

function iconClasses(name: string, animate: IconAnimate, className?: string) {
  return cn("app-icon", `app-icon-${name}`, `app-icon-${animate}`, className);
}

/** Shared wrapper for the app's own icon set (24x24 rounded line + soft fill
 *  in currentColor, so the sidebar's neon styles keep applying). */
function AppSvg({
  name,
  animate = "hover",
  className,
  children,
  ...rest
}: AppIconProps & { name: string; children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      data-icon-name={name}
      data-icon-animate={animate}
      className={iconClasses(name, animate, className)}
      {...rest}
    >
      {children}
    </svg>
  );
}

const HOME = "M4 11.2 12 4l8 7.2V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z";
export const HomeIcon: AppIconComponent = (props) => (
  <AppSvg name="home" {...props}>
    <g fill="currentColor" fillOpacity={0.2} stroke="none">
      <path d={HOME} />
    </g>
    <path
      className="app-icon-home-light"
      d="M9.75 20.5V15.5a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1v5z"
      fill="currentColor"
      stroke="none"
    />
    <circle
      className="app-icon-home-smoke app-icon-home-smoke-1"
      cx="16.5"
      cy="5.4"
      r="0.95"
      fill="currentColor"
      stroke="none"
    />
    <circle
      className="app-icon-home-smoke app-icon-home-smoke-2"
      cx="18.1"
      cy="3.7"
      r="0.7"
      fill="currentColor"
      stroke="none"
    />
    <path d={HOME} />
    <path d="M9.75 20.5V15.5a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1v5" />
  </AppSvg>
);

export const CalendarIcon: AppIconComponent = (props) => (
  <AppSvg name="calendar" {...props}>
    <g fill="currentColor" fillOpacity={0.2} stroke="none">
      <path d="M6.5 5h11a3 3 0 0 1 3 3v2h-17V8a3 3 0 0 1 3-3z" />
    </g>
    <rect
      className="app-icon-cal-page"
      x="4.5"
      y="10.2"
      width="15"
      height="9.2"
      rx="1.6"
      fill="currentColor"
      stroke="none"
    />
    <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
    <path d="M8 14h.01M16 14h.01M8 17h.01M12 17h.01" strokeWidth={2.2} />
    <path className="app-icon-cal-day" d="M12 14h.01" strokeWidth={2.2} />
  </AppSvg>
);

const STAR =
  "M11 4.5l1.8 5a3 3 0 0 0 1.8 1.8l5 1.7-5 1.7a3 3 0 0 0-1.8 1.8l-1.8 5-1.8-5a3 3 0 0 0-1.8-1.8l-5-1.7 5-1.7a3 3 0 0 0 1.8-1.8z";
export const AgentIcon: AppIconComponent = (props) => (
  <AppSvg name="agent" {...props}>
    <g className="app-icon-agent-star">
      <path d={STAR} fill="currentColor" fillOpacity={0.2} stroke="none" />
      <path d={STAR} />
    </g>
    <g className="app-icon-agent-spark">
      <path d="M19 3v4M17 5h4" />
    </g>
    <g className="app-icon-agent-spark-2">
      <path d="M4.5 17.5v2.4M3.3 18.7h2.4" strokeWidth={1.5} />
    </g>
  </AppSvg>
);

export const StatsIcon: AppIconComponent = (props) => (
  <AppSvg name="stats" {...props}>
    <g className="app-icon-stats-plot">
      <path
        d="M7.5 15.5l3.5-4 3 2.5 5-6.5V17H7.5z"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <path d="M7.5 15.5l3.5-4 3 2.5 5-6.5" />
    </g>
    <path d="M4 4v14a2 2 0 0 0 2 2h14" />
  </AppSvg>
);

export const MediaIcon: AppIconComponent = (props) => {
  const clipId = useId();
  return (
    <AppSvg name="media" {...props}>
      <defs>
        <clipPath id={clipId}>
          <rect x="3.5" y="4.5" width="17" height="15.5" rx="3" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <circle className="app-icon-media-sun" cx="8.5" cy="9" r="1.5" />
        <g className="app-icon-media-mountain">
          <path
            d="M3.5 16.5l5-4.5 3.5 3 3.5-4 5 5.5v.5a3 3 0 0 1-3 3h-11a3 3 0 0 1-3-3z"
            fill="currentColor"
            fillOpacity={0.2}
            stroke="none"
          />
          <path d="M3.5 16.5l5-4.5 3.5 3 3.5-4 5 5.5" />
        </g>
      </g>
      <rect x="3.5" y="4.5" width="17" height="15.5" rx="3" />
    </AppSvg>
  );
};

export const InboxIcon: AppIconComponent = (props) => (
  <AppSvg name="inbox" {...props}>
    <g className="app-icon-inbox-letter">
      <rect
        x="8"
        y="6.2"
        width="8"
        height="5.4"
        rx="1"
        fill="currentColor"
        fillOpacity={0.22}
        strokeWidth={1.4}
      />
      <path d="M8.5 6.8 12 9.5l3.5-2.7" strokeWidth={1.35} />
    </g>
    <g className="app-icon-inbox-tray">
      <path
        d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5V17a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 17z"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <path d="M3.5 13.5l2.6-7.2A2 2 0 0 1 8 5h8a2 2 0 0 1 1.9 1.3l2.6 7.2V17a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 17z" />
      <path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5" />
    </g>
  </AppSvg>
);

export const PeopleIcon: AppIconComponent = (props) => (
  <AppSvg name="people" {...props}>
    <g className="app-icon-people-main">
      <g fill="currentColor" fillOpacity={0.2} stroke="none">
        <circle cx="9" cy="8" r="3.5" />
        <path d="M3 19.5c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5z" />
      </g>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3 19.5c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5" />
    </g>
    <g className="app-icon-people-second">
      <path d="M16 4.8a3.3 3.3 0 0 1 0 6.4M17.5 14.4c1.9.6 3.1 2.4 3.5 5.1" />
    </g>
  </AppSvg>
);

export const BookIcon: AppIconComponent = (props) => (
  <AppSvg name="book" {...props}>
    <g className="app-icon-book-left">
      <path
        d="M12 7c-1.6-1.6-4-2.4-8.5-2.5V18c4.5.1 6.9.9 8.5 2.5z"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <path d="M12 7c-1.6-1.6-4-2.4-8.5-2.5V18c4.5.1 6.9.9 8.5 2.5" />
    </g>
    <g className="app-icon-book-right">
      <path d="M12 7c1.6-1.6 4-2.4 8.5-2.5V18c-4.5.1-6.9.9-8.5 2.5" />
    </g>
    <path d="M12 7v13.5" />
  </AppSvg>
);

const HORN = "M4 10.2v3.6a1 1 0 0 0 1 1h2.5L18 19.5v-15L7.5 9.2H5a1 1 0 0 0-1 1z";
export const MegaphoneIcon: AppIconComponent = (props) => (
  <AppSvg name="megaphone" {...props}>
    <g className="app-icon-megaphone-body">
      <path d={HORN} fill="currentColor" fillOpacity={0.2} stroke="none" />
      <path d={HORN} />
      <path d="M8 15l1.1 4.3a1 1 0 0 0 1 .7h.9a1 1 0 0 0 1-1.2l-.7-3" />
    </g>
    <path className="app-icon-megaphone-wave-1" d="M21 10v4" />
    <path
      className="app-icon-megaphone-wave-2"
      d="M20.4 8.2c1.4 1.8 1.4 5.8 0 7.6"
      strokeWidth={1.5}
    />
  </AppSvg>
);

export const BarsIcon: AppIconComponent = (props) => (
  <AppSvg name="bars" {...props}>
    <g className="app-icon-bar app-icon-bar-1">
      <rect
        x="4"
        y="12.5"
        width="4"
        height="7.5"
        rx="1.2"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <rect x="4" y="12.5" width="4" height="7.5" rx="1.2" />
    </g>
    <g className="app-icon-bar app-icon-bar-2">
      <rect
        x="10"
        y="4"
        width="4"
        height="16"
        rx="1.2"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <rect x="10" y="4" width="4" height="16" rx="1.2" />
    </g>
    <g className="app-icon-bar app-icon-bar-3">
      <rect
        x="16"
        y="8.5"
        width="4"
        height="11.5"
        rx="1.2"
        fill="currentColor"
        fillOpacity={0.2}
        stroke="none"
      />
      <rect x="16" y="8.5" width="4" height="11.5" rx="1.2" />
    </g>
  </AppSvg>
);

export const ClockIcon: AppIconComponent = (props) => (
  <AppSvg name="clock" {...props}>
    <g fill="currentColor" fillOpacity={0.2} stroke="none">
      <circle cx="12" cy="13" r="8" />
    </g>
    <circle cx="12" cy="13" r="8" />
    <path d="M5 3.5 2.5 6M19 3.5 21.5 6" />
    <path className="app-icon-clock-hour" d="M12 13l3 2" />
    <path className="app-icon-clock-min" d="M12 13V8.5" />
  </AppSvg>
);

export const UnassignedIcon: AppIconComponent = (props) => (
  <AppSvg name="unassigned" {...props}>
    <g className="app-icon-unassigned-person">
      <g fill="currentColor" fillOpacity={0.2} stroke="none">
        <circle cx="10" cy="8" r="3.5" />
        <path d="M3.5 20c.6-3.6 3.2-5.8 6.5-5.8 1.4 0 2.7.4 3.8 1.1V20z" />
      </g>
      <circle cx="10" cy="8" r="3.5" />
      <path d="M3.5 20c.6-3.6 3.2-5.8 6.5-5.8 1.4 0 2.7.4 3.8 1.1" />
    </g>
    <g className="app-icon-unassigned-x">
      <path d="M16.5 15.5l4 4M20.5 15.5l-4 4" />
    </g>
  </AppSvg>
);

const HG_TOP_BULB =
  "M8 3.5v3.2c0 1.4.7 2.7 1.9 3.5L12 12l2.1-1.8A4.2 4.2 0 0 0 16 6.7V3.5z";
const HG_BOTTOM_BULB =
  "M8 20.5v-3.2c0-1.4.7-2.7 1.9-3.5L12 12l2.1 1.8c1.2.8 1.9 2.1 1.9 3.5v3.2z";

export const HourglassIcon: AppIconComponent = (props) => {
  const id = useId();
  const topClip = `${id}-top`;
  const bottomClip = `${id}-bottom`;
  return (
    <AppSvg name="hourglass" {...props}>
      <defs>
        <clipPath id={topClip}>
          <path d={HG_TOP_BULB} />
        </clipPath>
        <clipPath id={bottomClip}>
          <path d={HG_BOTTOM_BULB} />
        </clipPath>
      </defs>
      <g className="app-icon-hg-body">
        <path
          d={HG_BOTTOM_BULB}
          fill="currentColor"
          fillOpacity={0.14}
          stroke="none"
        />
        <g clipPath={`url(#${topClip})`}>
          <rect
            className="app-icon-hg-sand-top"
            x="7.5"
            y="4"
            width="9"
            height="8"
            fill="currentColor"
            fillOpacity={0.55}
            stroke="none"
          />
        </g>
        <g clipPath={`url(#${bottomClip})`}>
          <rect
            className="app-icon-hg-sand-bottom"
            x="7.5"
            y="12"
            width="9"
            height="8.5"
            fill="currentColor"
            fillOpacity={0.55}
            stroke="none"
          />
        </g>
        <path
          className="app-icon-hg-stream"
          d="M12 11.6v7.4"
          strokeWidth={1.3}
        />
        <path d="M6.5 3.5h11M6.5 20.5h11" />
        <path d="M8 3.5v3.2c0 1.4.7 2.7 1.9 3.5L12 12l2.1-1.8A4.2 4.2 0 0 0 16 6.7V3.5" />
        <path d="M8 20.5v-3.2c0-1.4.7-2.7 1.9-3.5L12 12l2.1 1.8c1.2.8 1.9 2.1 1.9 3.5v3.2" />
      </g>
    </AppSvg>
  );
};

const BUBBLE =
  "M3.5 6.5A2.5 2.5 0 0 1 6 4h8a2.5 2.5 0 0 1 2.5 2.5v5A2.5 2.5 0 0 1 14 14H8.5L5 17v-3.1a2.5 2.5 0 0 1-1.5-2.4z";
export const MessagesIcon: AppIconComponent = (props) => (
  <AppSvg name="messages" {...props}>
    <g fill="currentColor" fillOpacity={0.2} stroke="none">
      <path d={BUBBLE} />
    </g>
    <path d={BUBBLE} />
    <path d="M20 8.5a2 2 0 0 1 .5 1.5v5a2.5 2.5 0 0 1-1.5 2.4V20l-3.5-3H11" />
    <g fill="currentColor" stroke="none">
      <circle className="app-icon-msg-dot app-icon-msg-dot-1" cx="7.4" cy="9" r="0.95" />
      <circle className="app-icon-msg-dot app-icon-msg-dot-2" cx="10" cy="9" r="0.95" />
      <circle className="app-icon-msg-dot app-icon-msg-dot-3" cx="12.6" cy="9" r="0.95" />
    </g>
  </AppSvg>
);

/** Instagram's own logo, in the text color so the sidebar's neon applies, and
 *  a little smaller: it fills its whole box, unlike the rest of the set. */
export const InstagramNavIcon: AppIconComponent = ({
  className,
  animate = "hover",
  ...props
}) => (
  <Instagram
    mono
    data-icon-name="instagram"
    data-icon-animate={animate}
    className={cn(
      "scale-[0.85] app-icon-brand",
      iconClasses("instagram", animate, className),
    )}
    {...props}
  />
);

/** WhatsApp's logo, same treatment as Instagram's. */
export const WhatsappNavIcon: AppIconComponent = ({
  className,
  animate = "hover",
  ...props
}) => (
  <WhatsApp
    mono
    data-icon-name="whatsapp"
    data-icon-animate={animate}
    className={cn(
      "scale-[0.85] app-icon-brand",
      iconClasses("whatsapp", animate, className),
    )}
    {...props}
  />
);

const SIDEBAR_PANE = "M6.5 4.5h3v15h-3a3 3 0 0 1-3-3v-9a3 3 0 0 1 3-3z";

export const SidebarCollapseIcon: AppIconComponent = (props) => (
  <AppSvg name="sidebar-collapse" {...props}>
    <path
      className="app-icon-sidebar-pane-collapse"
      d={SIDEBAR_PANE}
      fill="currentColor"
      fillOpacity={0.2}
      stroke="none"
    />
    <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
    <path d="M9.5 4.5v15" />
    <path
      className="app-icon-sidebar-chevron-left"
      d="M16 9.5 13.5 12l2.5 2.5"
    />
  </AppSvg>
);

export const SidebarExpandIcon: AppIconComponent = (props) => (
  <AppSvg name="sidebar-expand" {...props}>
    <path
      className="app-icon-sidebar-pane-expand"
      d={SIDEBAR_PANE}
      fill="currentColor"
      fillOpacity={0.2}
      stroke="none"
    />
    <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
    <path d="M9.5 4.5v15" />
    <path
      className="app-icon-sidebar-chevron-right"
      d="M13.5 9.5 16 12l-2.5 2.5"
    />
  </AppSvg>
);
