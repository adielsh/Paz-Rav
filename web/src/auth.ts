import { initializeApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type User,
} from "firebase/auth";
import { firebaseConfig } from "./firebaseConfig";

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
const provider = new GoogleAuthProvider();

export function signInWithGoogle(): Promise<unknown> {
  return signInWithPopup(auth, provider);
}

export function signOutUser(): Promise<void> {
  return signOut(auth);
}

/** Fires with the current user (or null) immediately, then on every change. */
export function watchAuthState(cb: (user: User | null) => void): () => void {
  return onAuthStateChanged(auth, cb);
}

/** A fresh ID token for the current user, or null if signed out. Firebase refreshes it
 * under the hood as needed — always call this right before a request, don't cache it. */
export async function currentIdToken(): Promise<string | null> {
  return auth.currentUser ? auth.currentUser.getIdToken() : null;
}
