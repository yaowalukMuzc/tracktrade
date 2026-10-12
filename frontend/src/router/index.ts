import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import type { NavId } from './nav'
import AppLayout from '@/layouts/AppLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** i18n key of the page title. */
    titleKey?: string
    /** Which nav item is highlighted. */
    nav?: NavId
    /** Spec features the screen implements (shown on placeholders). */
    features?: string
  }
}

const Placeholder = () => import('@/views/PlaceholderView.vue')

// Screens table in CLAUDE.md. Each screen replaces its Placeholder as it gets built.
const appRoutes: RouteRecordRaw[] = [
  { path: '', name: 'today', component: () => import('@/views/TodayView.vue'), meta: { titleKey: 'pages.today', nav: 'today', features: 'F-05, F-06, F-11 AC5, F-21' } },
  { path: 'analysis/:id', name: 'analysis', component: Placeholder, meta: { titleKey: 'pages.analysis', nav: 'today', features: 'F-05, F-19 AC3' } },
  { path: 'plans/:id', name: 'plan', component: Placeholder, meta: { titleKey: 'pages.plan', nav: 'today', features: 'F-06' } },
  { path: 'trades', name: 'trades', component: Placeholder, meta: { titleKey: 'pages.trades', nav: 'trades', features: 'F-07, F-10' } },
  { path: 'trades/new', name: 'trade-new', component: Placeholder, meta: { titleKey: 'pages.tradeNew', nav: 'trades', features: 'F-07, F-09' } },
  { path: 'trades/:id', name: 'trade-detail', component: Placeholder, meta: { titleKey: 'pages.tradeDetail', nav: 'trades', features: 'F-12 AC4, F-13, F-14, F-19' } },
  { path: 'trades/:id/review', name: 'trade-review', component: Placeholder, meta: { titleKey: 'pages.tradeReview', nav: 'trades', features: 'F-11 AC3, F-12' } },
  { path: 'calendar', name: 'calendar', component: Placeholder, meta: { titleKey: 'pages.calendar', nav: 'calendar', features: 'F-17' } },
  { path: 'stats', name: 'stats', component: Placeholder, meta: { titleKey: 'pages.stats', nav: 'stats', features: 'F-18' } },
  { path: 'diagnosis', name: 'diagnosis', component: Placeholder, meta: { titleKey: 'pages.diagnosis', nav: 'diagnosis', features: 'F-15, F-16' } },
  { path: 'playbook', name: 'playbook', component: Placeholder, meta: { titleKey: 'pages.playbook', nav: 'playbook', features: 'F-04' } },
  { path: 'accounts', name: 'accounts', component: Placeholder, meta: { titleKey: 'pages.accounts', nav: 'accounts', features: 'F-02, F-03, F-08' } },
  { path: 'alerts', name: 'alerts', component: Placeholder, meta: { titleKey: 'pages.alerts', nav: 'alerts', features: 'F-20, F-21' } },
  { path: 'settings', name: 'settings', component: Placeholder, meta: { titleKey: 'pages.settings', nav: 'settings', features: 'F-01, F-22' } },
  { path: 'mentor', name: 'mentor', component: Placeholder, meta: { titleKey: 'pages.mentor', nav: 'mentor', features: 'F-22 AC7' } },
  { path: 'mentor/queue', name: 'mentor-queue', component: Placeholder, meta: { titleKey: 'nav.mentorQueue', nav: 'mentorQueue', features: 'F-22' } },
  { path: 'mentor/trades/:id', name: 'mentor-trade', component: Placeholder, meta: { titleKey: 'pages.mentorTrade', nav: 'mentorQueue', features: 'F-22 AC2–AC4' } },
  { path: 'more', name: 'more', component: () => import('@/views/MoreView.vue'), meta: { titleKey: 'pages.more', nav: 'more' } },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Full-screen flows without the app shell.
    { path: '/login', name: 'login', component: Placeholder, meta: { titleKey: 'pages.login', features: 'F-01' } },
    { path: '/onboarding', name: 'onboarding', component: Placeholder, meta: { titleKey: 'pages.onboarding', features: 'F-01, F-02, F-08' } },
    { path: '/', component: AppLayout, children: appRoutes },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: Placeholder, meta: { titleKey: 'pages.notFound' } },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})
