import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import type { NavId } from './nav'
import { installGuards } from './guards'
import AppLayout from '@/layouts/AppLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** i18n key of the page title. */
    titleKey?: string
    /** Which nav item is highlighted. */
    nav?: NavId
    /** Spec features the screen implements (shown on placeholders). */
    features?: string
    /** Reachable without signing in. */
    public?: boolean
    /** Signed-in users are sent home (login/register). */
    guestOnly?: boolean
  }
}

const Placeholder = () => import('@/views/PlaceholderView.vue')

// Screens table in CLAUDE.md. Each screen replaces its Placeholder as it gets built.
const appRoutes: RouteRecordRaw[] = [
  { path: '', name: 'today', component: () => import('@/features/today/TodayView.vue'), meta: { titleKey: 'pages.today', nav: 'today', features: 'F-05, F-06, F-11 AC5, F-21' } },
  // `/analysis/new?symbol=&date=` and `/plans/new?analysis=` create on first save, then replace the URL with the id.
  { path: 'analysis/new', name: 'analysis-new', component: () => import('@/features/analysis/AnalysisView.vue'), meta: { titleKey: 'pages.analysis', nav: 'today', features: 'F-05, F-19 AC3' } },
  { path: 'analysis/:id', name: 'analysis', component: () => import('@/features/analysis/AnalysisView.vue'), meta: { titleKey: 'pages.analysis', nav: 'today', features: 'F-05, F-19 AC3' } },
  { path: 'plans/new', name: 'plan-new', component: () => import('@/features/plans/PlanView.vue'), meta: { titleKey: 'pages.plan', nav: 'today', features: 'F-06' } },
  { path: 'plans/:id', name: 'plan', component: () => import('@/features/plans/PlanView.vue'), meta: { titleKey: 'pages.plan', nav: 'today', features: 'F-06' } },
  // `/trades?tab=&match=<positionId>` — the match dialog opens over the list on desktop.
  { path: 'trades', name: 'trades', component: () => import('@/features/trades/TradesView.vue'), meta: { titleKey: 'pages.trades', nav: 'trades', features: 'F-07, F-10' } },
  // `?mode=manual|scan` (scan = Phase 5).
  { path: 'trades/new', name: 'trade-new', component: () => import('@/features/trade-new/AddTradeView.vue'), meta: { titleKey: 'pages.tradeNew', nav: 'trades', features: 'F-07, F-09' } },
  { path: 'trades/:id', name: 'trade-detail', component: Placeholder, meta: { titleKey: 'pages.tradeDetail', nav: 'trades', features: 'F-12 AC4, F-13, F-14, F-19' } },
  { path: 'trades/:id/review', name: 'trade-review', component: Placeholder, meta: { titleKey: 'pages.tradeReview', nav: 'trades', features: 'F-11 AC3, F-12' } },
  { path: 'calendar', name: 'calendar', component: Placeholder, meta: { titleKey: 'pages.calendar', nav: 'calendar', features: 'F-17' } },
  { path: 'stats', name: 'stats', component: Placeholder, meta: { titleKey: 'pages.stats', nav: 'stats', features: 'F-18' } },
  { path: 'diagnosis', name: 'diagnosis', component: Placeholder, meta: { titleKey: 'pages.diagnosis', nav: 'diagnosis', features: 'F-15, F-16' } },
  { path: 'playbook', name: 'playbook', component: () => import('@/features/playbook/PlaybookView.vue'), meta: { titleKey: 'pages.playbook', nav: 'playbook', features: 'F-04' } },
  // Mobile setup detail (screens/mobile/22-SetupDetail.png). ≥1024px shows the same setup inside /playbook (split view).
  { path: 'playbook/:id', name: 'setup-detail', component: () => import('@/features/playbook/SetupDetailView.vue'), meta: { titleKey: 'pages.playbook', nav: 'playbook', features: 'F-04' } },
  { path: 'accounts', name: 'accounts', component: () => import('@/features/accounts/AccountsView.vue'), meta: { titleKey: 'pages.accounts', nav: 'accounts', features: 'F-02, F-03, F-08' } },
  // Mobile connections page (screens/mobile/24-Connections.png); desktop shows it as the Connections tab of /accounts.
  { path: 'accounts/connections', name: 'account-connections', component: () => import('@/features/accounts/ConnectionsView.vue'), meta: { titleKey: 'connections.title', nav: 'accounts', features: 'F-08' } },
  { path: 'alerts', name: 'alerts', component: Placeholder, meta: { titleKey: 'pages.alerts', nav: 'alerts', features: 'F-20, F-21' } },
  { path: 'settings', name: 'settings', component: () => import('@/features/settings/SettingsView.vue'), meta: { titleKey: 'pages.settings', nav: 'settings', features: 'F-01, F-22' } },
  { path: 'mentor', name: 'mentor', component: Placeholder, meta: { titleKey: 'pages.mentor', nav: 'mentor', features: 'F-22 AC7' } },
  { path: 'mentor/queue', name: 'mentor-queue', component: Placeholder, meta: { titleKey: 'nav.mentorQueue', nav: 'mentorQueue', features: 'F-22' } },
  { path: 'mentor/trades/:id', name: 'mentor-trade', component: Placeholder, meta: { titleKey: 'pages.mentorTrade', nav: 'mentorQueue', features: 'F-22 AC2–AC4' } },
  { path: 'more', name: 'more', component: () => import('@/views/MoreView.vue'), meta: { titleKey: 'pages.more', nav: 'more' } },
]

const devRoutes: RouteRecordRaw[] = import.meta.env.DEV
  ? [{ path: '/dev/ui', name: 'dev-ui', component: () => import('@/views/DevUiView.vue'), meta: { titleKey: 'devUi.title', public: true } }]
  : []

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Full-screen flows without the app shell.
    { path: '/login', name: 'login', component: () => import('@/features/auth/LoginView.vue'), meta: { titleKey: 'pages.login', public: true, guestOnly: true } },
    { path: '/register', name: 'register', component: () => import('@/features/auth/RegisterView.vue'), meta: { titleKey: 'pages.register', public: true, guestOnly: true } },
    { path: '/forgot-password', name: 'forgot-password', component: () => import('@/features/auth/ForgotPasswordView.vue'), meta: { titleKey: 'pages.forgotPassword', public: true, guestOnly: true } },
    // Not guest-only: a signed-in user may open a reset link too (resetting signs every device out).
    { path: '/reset-password', name: 'reset-password', component: () => import('@/features/auth/ResetPasswordView.vue'), meta: { titleKey: 'pages.resetPassword', public: true } },
    { path: '/onboarding', name: 'onboarding', component: () => import('@/features/onboarding/OnboardingView.vue'), meta: { titleKey: 'pages.onboarding', features: 'F-01, F-02, F-08' } },
    // Mobile match queue, full screen "1 / 2" without the shell (screens/mobile/12-MatchQueue.png);
    // `?id=` starts at one trade. Desktop uses the modal on /trades.
    { path: '/trades/match', name: 'trade-match', component: () => import('@/features/trades/MatchQueueView.vue'), meta: { titleKey: 'trades.match.title', nav: 'trades', features: 'F-10' } },
    ...devRoutes,
    { path: '/', component: AppLayout, children: appRoutes },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: Placeholder, meta: { titleKey: 'pages.notFound' } },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

installGuards(router)
