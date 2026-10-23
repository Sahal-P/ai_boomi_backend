"use client";

import { Component, type ReactNode } from "react";

type WebGLBoundaryProps = { children: ReactNode; fallback?: ReactNode };
type WebGLBoundaryState = { failed: boolean };

/**
 * Contains WebGL failures (context creation, lost GPU, driver bugs) so a broken canvas
 * degrades to its CSS poster instead of taking the page down. React requires a class here.
 */
export class WebGLBoundary extends Component<WebGLBoundaryProps, WebGLBoundaryState> {
  state: WebGLBoundaryState = { failed: false };

  static getDerivedStateFromError(): WebGLBoundaryState {
    return { failed: true };
  }

  render() {
    return this.state.failed ? (this.props.fallback ?? null) : this.props.children;
  }
}
