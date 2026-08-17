import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChannelBadge, channelLabel } from "./channel-badge";

describe("ChannelBadge", () => {
  it("names the channel for anyone not reading colour", () => {
    // Icon-only in the row, so the accessible name is the only place the
    // channel is stated.
    render(<ChannelBadge channel="Channel::Instagram" />);
    expect(screen.getByRole("img", { name: "Instagram" })).toBeInTheDocument();
  });

  it("uses the name people use, not the stored one", () => {
    render(<ChannelBadge channel="Channel::Whatsapp" />);
    expect(screen.getByRole("img", { name: "WhatsApp" })).toBeInTheDocument();
  });

  it("renders nothing when the channel is unknown to the row", () => {
    const { container } = render(<ChannelBadge channel={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("still shows something for a channel it has no icon for", () => {
    // A channel added later must not leave a blank gap in the column.
    render(<ChannelBadge channel="Channel::SomethingNew" />);
    expect(
      screen.getByRole("img", { name: "SomethingNew" }),
    ).toBeInTheDocument();
  });

  it("labels the known channels", () => {
    expect(channelLabel("Channel::FacebookPage")).toBe("Facebook");
    expect(channelLabel("Channel::TwilioSms")).toBe("SMS");
    expect(channelLabel(null)).toBeNull();
  });
});
