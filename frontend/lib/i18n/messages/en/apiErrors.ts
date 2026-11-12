import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "You don't have permission to do this.",
  tooManyAttempts: "Too many failed attempts. Wait a few minutes and try again.",
  mediaUnsupported: "Unsupported format. Upload an image or a video.",
  imageTooBig: "The image exceeds the 30 MB limit.",
  videoTooBig: "The video exceeds the 200 MB limit.",
  uploadFailed: "Couldn't upload the file ({status}).",
  pushDenied: "Notification permission denied.",
  agentFailed: "Something went wrong talking to the agent.",
  requestFailed: "Something went wrong processing the request.",
  requestFailedStatus: "The request failed ({status}).",
};
