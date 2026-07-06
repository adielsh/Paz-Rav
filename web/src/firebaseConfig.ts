// Firebase web config is NOT secret — Google's own docs say it's fine to ship this in
// client code (access control happens via Firebase's own rules/OAuth, not by hiding
// this object). Fill in with the values from:
// Firebase console → Project Settings → your web app → "SDK setup and configuration".
export const firebaseConfig = {
  apiKey: "AIzaSyDZp_07fCkL0w9iCne3VffQIggRLnjfNHY",
  authDomain: "pazrav.firebaseapp.com",
  projectId: "pazrav",
  appId: "1:235527448594:web:dbb51a3e0cb40c908dd0cb",
};
