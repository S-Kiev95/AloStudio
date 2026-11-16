import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar, initialsFor } from "./avatar";

describe("initialsFor", () => {
  it("takes the first and last word", () => {
    expect(initialsFor("Lucía Pereira")).toBe("LP");
  });

  it("skips symbols and asides in brackets", () => {
    expect(initialsFor("Lucía Pereira (demo)")).toBe("LP");
    expect(initialsFor("Lucía Pereira [prueba] ")).toBe("LP");
    expect(initialsFor("Lucía Pereira - ")).toBe("LP");
    // Nothing but the aside: better its letter than a question mark.
    expect(initialsFor("(Lucía)")).toBe("L");
  });

  it("falls back to a question mark", () => {
    expect(initialsFor("")).toBe("?");
    expect(initialsFor("  ()  ")).toBe("?");
  });

  it("keeps digits, for placeholder names", () => {
    expect(initialsFor("instagram-123456")).toBe("I");
    expect(initialsFor("+598 99 123")).toBe("51");
  });
});

describe("Avatar", () => {
  it("shows the picture over the initials", () => {
    const { container } = render(<Avatar name="Ana Sosa" src="/pic" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/pic");
    expect(container.textContent).toBe("AS");
  });

  it("drops a picture that fails to load", () => {
    const { container } = render(<Avatar name="Ana Sosa" src="/broken" />);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toBe("AS");
  });

  it("has no img without a picture", () => {
    const { container } = render(<Avatar name="Ana Sosa" src="" />);
    expect(container.querySelector("img")).toBeNull();
  });
});
