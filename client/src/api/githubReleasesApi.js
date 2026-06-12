import axios from "axios";

const githubClient = axios.create({
  baseURL: "https://api.github.com/repos/giuseppe99barchetta/SuggestArr",
  timeout: 8000,
  withCredentials: false,
});

export const getLatestRelease = () => githubClient.get("/releases/latest");

export const getReleaseByTag = (tag) =>
  githubClient.get(`/releases/tags/${encodeURIComponent(tag)}`);
