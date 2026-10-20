<template>
  <div class="text-ink" data-users-page>

    <PageHeader title="Users" subtitle="SuggestArr accounts, their roles and who can sign up. Your own settings are under Profile." />

    <dl aria-label="Account overview" class="m-0 mb-5 flex flex-wrap gap-2">
      <div v-for="stat in accountStats" :key="stat.key" class="relative flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm" :class="isStatActive(stat) ? 'border-brand bg-brand-soft' : 'border-edge bg-panel hover:border-edge-strong'">
        <i aria-hidden="true" class="text-xs" :class="[stat.icon, stat.tone]"></i>
        <dt class="order-last text-ink-3"><button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-inherit after:absolute after:inset-0 after:rounded-full" :aria-pressed="isStatActive(stat) ? 'true' : 'false'" :disabled="isLoadingUsers || usersError" @click="applyStat(stat)">{{ stat.label }}</button></dt>
        <dd class="m-0 font-extrabold text-ink">{{ isLoadingUsers || usersError ? '—' : stat.value }}</dd>
      </div>
    </dl>

    <div data-users-cards class="mb-8 grid items-stretch gap-5 min-[1001px]:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">

      <SectionCard icon="fas fa-users" title="Accounts">
        <template #actions>
          <button type="button" class="ui-btn h-9" @click="openCreateModal">
            <i aria-hidden="true" class="fas fa-user-plus"></i>
            New User
          </button>
        </template>

        <!-- Loading -->
        <p v-if="isLoadingUsers && !users.length" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
          Loading users…
        </p>

        <div v-else-if="usersError" role="alert" class="ui-alert-bad flex flex-wrap items-center justify-between gap-3">
          <span>Could not load accounts. Try again to see the latest account details.</span>
          <button type="button" class="ui-btn h-9" @click="loadUsers">Try again</button>
        </div>

        <!-- Empty -->
        <p v-else-if="users.length === 0" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-users"></i>
          No accounts found.
        </p>

        <div v-else class="flex flex-col gap-4">
          <div class="flex flex-wrap items-center gap-3">
            <label class="relative min-w-0 flex-[1_1_200px]">
              <span class="sr-only">Find an account</span>
              <i aria-hidden="true" class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-sm text-ink-4"></i>
              <input v-model="userQuery" type="search" class="ui-input pl-9" placeholder="Find an account…" />
            </label>
            <label class="ui-label flex-[0_1_150px]">
              <span class="sr-only">Filter accounts by role</span>
              <select v-model="roleFilter" class="ui-input"><option value="all">All roles</option><option value="admin">Admins</option><option value="user">Users</option></select>
            </label>
            <div role="group" aria-label="Account layout" class="flex gap-1">
              <button v-for="mode in viewModes" :key="mode.value" type="button" class="ui-btn h-[42px] w-[42px] px-0" :class="{ 'border-brand text-brand-ink': viewMode === mode.value }" :aria-label="mode.label" :title="mode.label" :aria-pressed="viewMode === mode.value ? 'true' : 'false'" @click="setViewMode(mode.value)"><i aria-hidden="true" :class="mode.icon"></i></button>
            </div>
          </div>
          <p v-if="!filteredUsers.length" role="status" :class="emptyClass">No accounts match your filters.<button type="button" class="cursor-pointer border-0 bg-transparent text-sm font-semibold text-brand-ink" @click="resetFilters">Clear filters</button></p>

          <ul v-else-if="viewMode === 'list'" class="m-0 flex list-none flex-col divide-y divide-edge rounded-card border border-edge-strong bg-panel-2 p-0">
            <li v-for="user in filteredUsers" :key="user.id">
              <article :aria-label="`Account ${user.username}`" class="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5" :class="{ 'opacity-70': !user.is_active }">
                <div class="flex min-w-0 flex-[1_1_180px] items-center gap-3">
                  <UserAvatar :user="user" class="h-9 w-9" />
                  <div class="min-w-0">
                    <h3 class="m-0 flex items-center gap-1.5 text-sm font-bold text-ink"><span class="truncate" :title="user.username">{{ user.username }}</span><span v-if="isSelf(user)" class="shrink-0 rounded-full bg-brand px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">you</span></h3>
                    <p class="m-0 text-xs text-ink-3">{{ user.role === 'admin' ? 'Administrator' : 'User' }} · <span :title="formatDate(user.last_login)">{{ user.last_login ? `seen ${relativeTime(user.last_login)}` : 'never signed in' }}</span></p>
                  </div>
                </div>
                <span class="text-xs text-ink-3" :title="pagesTitle(user)">{{ pagesSummary(user) }}</span>
                <div class="flex items-center gap-1">
                  <button v-if="supportsUserLinks" type="button" :disabled="!!isSaving[user.id]" :aria-label="`Assign ${providerLabel} account to ${user.username}`" :title="`${providerLabel}: ${mediaName(user) || 'not linked'}`" class="ui-btn h-8 w-8 px-0" @click="openMediaLinkModal(user)"><i aria-hidden="true" class="fas fa-link" :class="mediaProfile(user) ? 'text-good' : 'text-ink-4'"></i></button>
                  <button type="button" :disabled="!!isSaving[user.id]" :aria-label="`Edit Seer identity for ${user.username}`" :title="`Seer: ${seerIdentity(user)}`" class="ui-btn h-8 w-8 px-0" @click="openEditPermissionsModal(user)"><i aria-hidden="true" class="fas fa-ticket-alt" :class="user.seer_user_id != null ? 'text-brand-ink' : 'text-ink-4'"></i></button>
                </div>
                <div class="ml-auto flex items-center gap-2">
                  <button type="button" :disabled="statusLocked(user) || !!isSaving[user.id]" :aria-label="`${user.is_active ? 'Deactivate' : 'Activate'} ${user.username}`" :title="statusTitle(user)" :class="statusClass(user)" @click="toggleActive(user)"><span aria-hidden="true" class="h-1.5 w-1.5 rounded-full" :class="user.is_active ? 'bg-good' : 'bg-ink-4'"></span>{{ user.is_active ? 'Enabled' : 'Disabled' }}</button>
                  <button type="button" :disabled="!!isSaving[user.id]" class="ui-btn h-8 w-8 px-0" :aria-label="`Edit permissions for ${user.username}`" title="Role & permissions" @click="openEditPermissionsModal(user)"><i aria-hidden="true" class="fas fa-sliders-h"></i></button>
                  <button type="button" :disabled="statusLocked(user) || !!isSaving[user.id]" class="ui-btn-icon-danger h-8" :aria-label="`Delete ${user.username}`" :title="deleteTitle(user)" @click="confirmDelete(user)"><i aria-hidden="true" class="fas fa-trash"></i></button>
                </div>
              </article>
            </li>
          </ul>

          <div v-else class="grid gap-4 min-[700px]:grid-cols-2 min-[1001px]:grid-cols-1 min-[1280px]:grid-cols-2">
            <article v-for="user in filteredUsers" :key="user.id" :aria-label="`Account ${user.username}`" class="flex min-w-0 flex-col rounded-card border border-edge-strong bg-panel-2 p-4" :class="{ 'opacity-70': !user.is_active }">
              <div class="flex items-start gap-3">
                <UserAvatar :user="user" class="h-12 w-12" />
                <div class="min-w-0 flex-1">
                  <h3 class="m-0 flex items-center gap-1.5 text-base font-bold text-ink"><span class="truncate" :title="user.username">{{ user.username }}</span><span v-if="isSelf(user)" class="shrink-0 rounded-full bg-brand px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">you</span></h3>
                  <p class="m-0 mt-1 text-xs text-ink-3"><i aria-hidden="true" :class="user.role === 'admin' ? 'fas fa-user-shield' : 'fas fa-user'" class="mr-1.5"></i>{{ user.role === 'admin' ? 'Administrator' : 'User' }}</p>
                </div>
                <button type="button" :disabled="statusLocked(user) || !!isSaving[user.id]" :aria-label="`${user.is_active ? 'Deactivate' : 'Activate'} ${user.username}`" :title="statusTitle(user)" :class="statusClass(user)" @click="toggleActive(user)"><span aria-hidden="true" class="h-1.5 w-1.5 rounded-full" :class="user.is_active ? 'bg-good' : 'bg-ink-4'"></span>{{ user.is_active ? 'Enabled' : 'Disabled' }}</button>
              </div>

              <dl class="m-0 mt-4 grid grid-cols-2 gap-3 border-t border-edge pt-3 text-xs">
                <div class="min-w-0"><dt class="text-ink-4">Last login</dt><dd class="m-0 mt-1 leading-relaxed text-ink-2" :title="user.last_login ? formatDate(user.last_login) : null">{{ user.last_login ? relativeTime(user.last_login) : 'Never' }}</dd></div>
                <div class="min-w-0"><dt class="text-ink-4">Member since</dt><dd class="m-0 mt-1 leading-relaxed text-ink-2">{{ user.created_at ? formatDate(user.created_at, false) : 'Not available' }}</dd></div>
              </dl>

              <div class="mt-4 flex flex-wrap gap-1.5" :aria-label="`Page access for ${user.username}`">
                <span class="inline-flex items-center gap-1.5 rounded-md bg-canvas/70 px-2 py-1 text-[11px] font-semibold text-ink-2" :title="pagesTitle(user)"><i aria-hidden="true" class="fas fa-layer-group text-ink-4"></i>{{ pagesSummary(user) }}</span>
                <span v-if="user.role === 'admin' || user.can_manage_ai" class="inline-flex items-center gap-1.5 rounded-md bg-brand-soft/60 px-2 py-1 text-[11px] font-semibold text-brand-ink"><i aria-hidden="true" class="fas fa-robot"></i>AI settings</span>
              </div>

              <div class="mb-4 mt-3 flex gap-2">
                <button v-if="supportsUserLinks" type="button" :disabled="!!isSaving[user.id]" :aria-label="`Assign ${providerLabel} account to ${user.username}`" :title="`${providerLabel} account: ${mediaName(user) || 'not linked'}`" class="flex min-w-0 flex-1 basis-0 cursor-pointer items-center gap-2 rounded-ctl border border-edge bg-canvas/50 px-2.5 py-2 text-left hover:border-brand-ink disabled:opacity-50" @click="openMediaLinkModal(user)">
                  <i aria-hidden="true" class="fas fa-link w-4 shrink-0 text-center" :class="mediaProfile(user) ? 'text-good' : 'text-ink-4'"></i>
                  <span class="truncate text-xs font-semibold" :class="mediaProfile(user) ? 'text-ink-2' : 'text-ink-4'">{{ mediaName(user) || `Link ${providerLabel}` }}</span>
                </button>
                <button type="button" :disabled="!!isSaving[user.id]" :aria-label="`Edit Seer identity for ${user.username}`" :title="`Seer request identity: ${seerIdentity(user)}`" class="flex min-w-0 flex-1 basis-0 cursor-pointer items-center gap-2 rounded-ctl border border-edge bg-canvas/50 px-2.5 py-2 text-left hover:border-brand-ink disabled:opacity-50" @click="openEditPermissionsModal(user)">
                  <i aria-hidden="true" class="fas fa-ticket-alt w-4 shrink-0 text-center" :class="user.seer_user_id != null ? 'text-brand-ink' : 'text-ink-4'"></i>
                  <span class="truncate text-xs font-semibold" :class="user.seer_user_id != null ? 'text-ink-2' : 'text-ink-4'">{{ seerIdentity(user) }}</span>
                </button>
              </div>

              <div class="mt-auto flex items-center gap-2 border-t border-edge pt-3">
                <button type="button" :disabled="!!isSaving[user.id]" class="ui-btn h-[42px] flex-1 px-3 text-xs" :aria-label="`Edit permissions for ${user.username}`" @click="openEditPermissionsModal(user)"><i aria-hidden="true" class="fas fa-sliders-h"></i>Role &amp; permissions</button>
                <button type="button" :disabled="statusLocked(user) || !!isSaving[user.id]" class="ui-btn-icon-danger h-[42px]" :aria-label="`Delete ${user.username}`" :title="deleteTitle(user)" @click="confirmDelete(user)"><i aria-hidden="true" class="fas fa-trash"></i></button>
              </div>
            </article>
          </div>
        </div>
      </SectionCard>

      <SectionCard icon="fas fa-door-open" title="Self-Registration">
        <button type="button" role="switch" :aria-checked="localAllowRegistration ? 'true' : 'false'" :disabled="isSavingRegistration" class="flex w-full cursor-pointer items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3.5 text-left hover:border-edge-strong disabled:cursor-not-allowed disabled:opacity-50" @click="saveRegistration({ localAllowRegistration: !localAllowRegistration })">
          <span class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">Allow sign-ups</span>
            <span class="text-xs leading-snug text-ink-4">Anyone who can reach the login page can create a User account.</span>
          </span>
          <span class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors" :class="localAllowRegistration ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="localAllowRegistration ? 'left-[21px]' : 'left-[3px]'"></span></span>
        </button>

        <fieldset v-if="localAllowRegistration" class="m-0 mt-4 flex flex-col gap-2 border-0 p-0" :disabled="isSavingRegistration">
          <legend class="mb-2 p-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Pages for new accounts</legend>
          <label v-for="tab in availableTabs" :key="tab.value" class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 px-3 py-2 text-sm text-ink-2" :class="tab.required ? 'opacity-60' : 'cursor-pointer hover:border-ink-4'">
            <input type="checkbox" class="accent-brand" :checked="tab.required || registrationTabs.includes(tab.value)" :disabled="tab.required" @change="toggleRegistrationTab(tab.value)" />
            <i aria-hidden="true" class="w-4 text-center text-ink-4" :class="tab.icon"></i>
            <span class="flex-1">{{ tab.label }}</span>
          </label>
        </fieldset>
        <p v-else class="m-0 mt-4 text-xs leading-relaxed text-ink-4"><i aria-hidden="true" class="fas fa-lock mr-1.5"></i>Only admins add accounts, with New User.</p>
      </SectionCard>

    </div>

    <AppDialog v-if="showCreateModal" width="max-w-2xl" title="Create account" subtitle="A new SuggestArr login. Share the password with the person securely." icon="fas fa-user-plus" @close="showCreateModal = false">
      <form id="create-user-form" class="flex flex-col gap-4" @submit.prevent="submitCreate">
        <label class="ui-label">Username
          <input v-model="newUser.username" type="text" class="ui-input" placeholder="e.g. alex" maxlength="64" autocomplete="off" :disabled="isCreating" />
        </label>
        <div class="ui-label">
          <label for="newPassword">Password</label>
          <div class="flex gap-2">
            <input id="newPassword" v-model="newUser.password" :type="showNewPassword ? 'text' : 'password'" class="ui-input" placeholder="At least 8 characters" autocomplete="new-password" :disabled="isCreating" />
            <button type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isCreating" :aria-label="showNewPassword ? 'Hide password' : 'Show password'" @click="showNewPassword = !showNewPassword">
              <i aria-hidden="true" :class="showNewPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <span class="text-xs font-normal" :class="newUser.password && newUser.password.length < 8 ? 'text-caution' : 'text-ink-4'">
            {{ newUser.password && newUser.password.length < 8 ? 'Use at least 8 characters.' : 'Mix letters, numbers and symbols.' }}
          </span>
        </div>
        <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-1.5 p-0 text-[13px] font-semibold text-ink-2">Role</legend>
          <label v-for="role in roleOptions" :key="role.value" class="flex cursor-pointer items-start gap-3 rounded-ctl border p-3" :class="newUser.role === role.value ? 'border-brand bg-brand-soft' : 'border-edge-strong bg-panel-2 hover:border-ink-4'">
            <input v-model="newUser.role" type="radio" name="new-user-role" :value="role.value" class="mt-0.5 accent-brand" :disabled="isCreating" />
            <span class="text-sm font-semibold text-ink">{{ role.label }}<span class="block text-xs font-normal text-ink-3">{{ role.description }}</span></span>
          </label>
        </fieldset>
        <p v-if="createError" class="ui-alert-bad" role="alert">{{ createError }}</p>
      </form>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isCreating" @click="showCreateModal = false">Cancel</button>
        <button type="submit" form="create-user-form" class="ui-btn-primary" :disabled="isCreating">
          <i v-if="isCreating" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isCreating ? 'Creating…' : 'Create account' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showDeleteModal" title="Delete account" icon="fas fa-trash" tone="danger" @close="showDeleteModal = false">
      <p class="m-0 text-sm leading-relaxed text-ink-2">Permanently delete <strong class="text-ink">{{ deleteTarget?.username }}</strong>? They lose access immediately. This cannot be undone.</p>
      <p v-if="deleteTarget?.is_active" class="m-0 mt-3 text-xs text-ink-3">To keep their history and links, disable the account instead.</p>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isDeleting" @click="showDeleteModal = false">Cancel</button>
        <button type="button" class="ui-btn-danger" :disabled="isDeleting" @click="submitDelete">
          <i v-if="isDeleting" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isDeleting ? 'Deleting…' : 'Delete account' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showPermissionsModal" width="max-w-3xl" title="Permissions" icon="fas fa-user-shield" @close="showPermissionsModal = false">
      <template #subtitle>
        Role, pages and Seer identity for {{ permissionsTarget?.username }}
      </template>
      <div class="flex flex-col gap-6">
        <fieldset class="m-0 flex flex-col gap-2 border-0 p-0" :disabled="isSavingPermissions || !!roleLockReason(permissionsTarget)">
          <legend class="mb-2 p-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Role</legend>
          <div class="grid gap-2 sm:grid-cols-2">
            <label v-for="role in roleOptions" :key="role.value" class="flex items-start gap-3 rounded-ctl border p-3" :class="[editPermissions.role === role.value ? 'border-brand bg-brand-soft' : 'border-edge-strong bg-panel-2', roleLockReason(permissionsTarget) ? 'opacity-60' : 'cursor-pointer hover:border-ink-4']">
              <input v-model="editPermissions.role" type="radio" name="edit-user-role" :value="role.value" class="mt-0.5 accent-brand" />
              <span class="text-sm font-semibold text-ink">{{ role.label }}<span class="block text-xs font-normal text-ink-3">{{ role.description }}</span></span>
            </label>
          </div>
          <p v-if="roleLockReason(permissionsTarget)" class="m-0 text-xs text-ink-4"><i aria-hidden="true" class="fas fa-lock mr-1.5"></i>{{ roleLockReason(permissionsTarget) }}</p>
        </fieldset>

        <p v-if="editPermissions.role === 'admin'" class="m-0 rounded-ctl border border-edge bg-canvas/50 p-3 text-xs text-ink-3">Admins see every page and can manage AI settings.</p>

        <section v-if="editPermissions.role !== 'admin'" class="flex flex-col gap-3">
          <h3 class="m-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Features</h3>
          <BaseCheckbox
            v-model="editPermissions.can_manage_ai"
            :disabled="isSavingPermissions"
            label="Can manage AI settings"
            description="Lets this user set their own AI provider and key."
          />
        </section>

        <section class="flex flex-col gap-2">
          <h3 class="m-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Seer identity</h3>
          <p class="m-0 text-[13px] text-ink-3">Approved requests are credited to this Seer user.</p>
          <select v-model="editPermissions.seer_user_id" class="ui-input" aria-label="Seer identity" :disabled="isSavingPermissions">
            <option v-for="option in seerUserOptions" :key="option.value ?? 'fallback'" :value="option.value">{{ option.label }}</option>
          </select>
        </section>

        <fieldset v-if="editPermissions.role !== 'admin'" class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-2 p-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Visible pages</legend>
          <div class="grid gap-2 sm:grid-cols-2">
            <label
              v-for="tab in availableTabs"
              :key="tab.value"
              class="flex items-center gap-3 rounded-ctl border border-edge-strong bg-panel-2 px-3 py-2.5 text-sm text-ink-2"
              :class="tab.required ? 'opacity-60' : 'cursor-pointer hover:border-ink-4'"
            >
              <input
                type="checkbox"
                class="accent-brand"
                :value="tab.value"
                :checked="editPermissions.visible_tabs_array.includes(tab.value)"
                :disabled="isSavingPermissions || tab.required"
                @change="toggleTab(tab.value)"
              />
              <i aria-hidden="true" class="w-4 text-center text-ink-4" :class="tab.icon"></i>
              <span class="flex-1">{{ tab.label }}</span>
              <span v-if="tab.required" class="text-[10px] font-bold uppercase tracking-wide text-ink-4">Always</span>
            </label>
          </div>
        </fieldset>

        <p v-if="permissionsError" class="ui-alert-bad" role="alert">{{ permissionsError }}</p>
      </div>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isSavingPermissions" @click="showPermissionsModal = false">Cancel</button>
        <button type="button" class="ui-btn-primary" :disabled="isSavingPermissions" @click="submitPermissions">
          <i v-if="isSavingPermissions" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingPermissions ? 'Saving…' : 'Save permissions' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showMediaLinkModal" title="Link media account" icon="fas fa-link" :subtitle="mediaLinkSubtitle" @close="showMediaLinkModal = false">
      <div class="flex flex-col gap-3">
        <label class="ui-label">
          {{ providerLabel }} user
          <select v-model="selectedMediaUserId" class="ui-input" :disabled="isLoadingMediaUsers || isSavingMediaLink">
            <option value="" disabled>Select account</option>
            <option v-for="option in mediaUserOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
        <p v-if="isLoadingMediaUsers" class="m-0 text-xs text-ink-4"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-1"></i>Loading {{ providerLabel }} users…</p>
        <p v-if="mediaLinkError" class="ui-alert-bad" role="alert">{{ mediaLinkError }}</p>
      </div>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isSavingMediaLink" @click="showMediaLinkModal = false">Cancel</button>
        <button type="button" class="ui-btn-primary" :disabled="isSavingMediaLink || !selectedMediaUserId" @click="submitMediaLink">
          <i v-if="isSavingMediaLink" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingMediaLink ? 'Saving…' : 'Save link' }}
        </button>
      </template>
    </AppDialog>

  </div>
</template>

<script>
import { useAuth } from '@/composables/useAuth';
import {
  adminLinkProvider,
  createUserAdmin,
  deleteUser,
  fetchPlexUsers,
  getMediaServerUsers,
  getUsers,
  updateUser,
  updateUserPermissions,
} from '@/api/api';
import axios from 'axios';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import PageHeader from '@/components/ui/PageHeader.vue';
import AppDialog from '@/components/ui/AppDialog.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import UserAvatar from '@/components/ui/UserAvatar.vue';
import { refreshUserAvatar } from '@/composables/useUserAvatar';

const DEFAULT_TABS = 'requests,jobs,profile';
const VIEW_MODE_KEY = 'suggestarr.users.view';

function splitTabs(tabs) {
  return (Array.isArray(tabs) ? tabs : String(tabs || '').split(',')).map(tab => String(tab).trim()).filter(Boolean);
}

function readViewMode() {
  try { return localStorage.getItem(VIEW_MODE_KEY) === 'list' ? 'list' : 'cards'; } catch { return 'cards'; }
}

export default {
  name: 'UserManagement',

  components: { AppDialog, BaseCheckbox, PageHeader, SectionCard, UserAvatar },

  props: {
    config: Object,
    isLoading: Boolean,
  },

  setup() {
    const { currentUser } = useAuth();
    return { currentUser };
  },

  data() {
    return {
      users: [],
      userQuery: '',
      roleFilter: 'all',
      quickFilter: '',
      viewMode: readViewMode(),
      viewModes: [
        { value: 'cards', label: 'Card view', icon: 'fas fa-th-large' },
        { value: 'list', label: 'List view', icon: 'fas fa-list' },
      ],
      usersError: false,
      emptyClass: 'm-0 flex items-center justify-center gap-3 rounded-[8px] border border-dashed border-edge-strong px-4 py-8 text-[0.95rem] text-ink-4',
      isLoadingUsers: true,
      isSaving: {},
      localAllowRegistration: false,
      registrationTabs: [],
      isSavingRegistration: false,

      // Create modal
      showCreateModal: false,
      newUser: { username: '', password: '', role: 'user' },
      showNewPassword: false,
      createError: null,
      isCreating: false,

      // Delete modal
      showDeleteModal: false,
      deleteTarget: null,
      isDeleting: false,

      // Permissions modal
      showPermissionsModal: false,
      permissionsTarget: null,
      editPermissions: {
        role: 'user',
        can_manage_ai: false,
        visible_tabs_array: [],
        seer_user_id: null,
      },
      seerUsers: [],
      permissionsError: null,
      isSavingPermissions: false,

      showMediaLinkModal: false,
      mediaLinkTarget: null,
      mediaUsers: [],
      selectedMediaUserId: '',
      isLoadingMediaUsers: false,
      isSavingMediaLink: false,
      mediaLinkError: null,

      roleOptions: [
        { label: 'Admin', value: 'admin', description: 'Full access, including settings and other accounts.' },
        { label: 'User', value: 'user', description: 'Only the pages you enable. Profile is always available.' },
      ],

      availableTabs: [
        { value: 'requests', label: 'Requests', icon: 'fas fa-film', required: false },
        { value: 'jobs', label: 'Jobs', icon: 'fas fa-briefcase', required: false },
        { value: 'ai_search', label: 'AI Search', icon: 'fas fa-robot', required: false },
        { value: 'profile', label: 'Profile', icon: 'fas fa-user-circle', required: true },
      ],
    };
  },

  computed: {
    accountStats() {
      return [
        { key: 'all', label: 'accounts', value: this.users.length, icon: 'fas fa-users', tone: 'text-brand-ink' },
        { key: 'enabled', label: 'enabled', value: this.users.filter(user => user.is_active).length, icon: 'fas fa-user-check', tone: 'text-good' },
        { key: 'admin', label: 'admins', value: this.users.filter(user => user.role === 'admin').length, icon: 'fas fa-user-shield', tone: 'text-notice' },
        { key: 'linked', label: this.supportsUserLinks ? `linked to ${this.providerLabel}` : 'media accounts linked', value: this.users.filter(user => this.mediaProfile(user)).length, icon: 'fas fa-link', tone: 'text-caution' },
      ];
    },
    filteredUsers() {
      const query = this.userQuery.trim().toLocaleLowerCase();
      return this.users.filter(user =>
        (this.roleFilter === 'all' || user.role === this.roleFilter) &&
        (!this.quickFilter || (this.quickFilter === 'enabled' ? user.is_active : !!this.mediaProfile(user))) &&
        (!query || [user.username, ...((user.media_profiles || []).map(profile => profile.external_username))]
          .some(name => String(name || '').toLocaleLowerCase().includes(query)))
      );
    },
    activeAdminCount() {
      return this.users.filter(user => user.role === 'admin' && user.is_active).length;
    },
    currentUserId() {
      if (!this.currentUser) return null;
      return Number(this.currentUser.id ?? this.currentUser.sub ?? null);
    },
    selectedService() {
      return (this.config?.SELECTED_SERVICE || '').toLowerCase();
    },
    supportsUserLinks() {
      return ['jellyfin', 'emby', 'plex'].includes(this.selectedService);
    },
    providerLabel() {
      const labels = { plex: 'Plex', jellyfin: 'Jellyfin', emby: 'Emby' };
      return labels[this.selectedService] || 'media';
    },
    mediaLinkSubtitle() {
      return `Which ${this.providerLabel} user's watch history belongs to ${this.mediaLinkTarget?.username}.`;
    },
    mediaUserOptions() {
      return this.mediaUsers.map((user) => ({
        label: user.name || user.username || user.title || user.email || String(user.id),
        value: String(user.id),
      }));
    },
    seerUserOptions() {
      return [{ label: 'Technical user fallback', value: null }, ...this.seerUsers.map(user => ({ label: user.displayName || user.username || user.email || String(user.id), value: user.id }))];
    },
    selectedMediaUser() {
      return this.mediaUsers.find((user) => String(user.id) === String(this.selectedMediaUserId)) || null;
    },
  },

  watch: {
    'config.ALLOW_REGISTRATION': {
      immediate: true,
      handler(val) {
        this.localAllowRegistration = !!val;
      },
    },
    'config.REGISTRATION_DEFAULT_TABS': {
      immediate: true,
      handler(val) {
        this.registrationTabs = splitTabs(val ?? DEFAULT_TABS);
      },
    },
  },

  mounted() {
    this.loadUsers();
    this.loadSeerUsers();
  },

  methods: {
    mediaProfile(user) {
      return (user.media_profiles || []).find(profile => this.supportsUserLinks ? profile.provider === this.selectedService : ['plex', 'jellyfin', 'emby'].includes(profile.provider));
    },
    isSelf(user) {
      return Number(user.id) === this.currentUserId;
    },
    isLastAdmin(user) {
      return user.role === 'admin' && user.is_active && this.activeAdminCount <= 1;
    },
    // Mirrors the API guards so the UI never offers an action the server refuses.
    statusLocked(user) {
      return this.isSelf(user) || this.isLastAdmin(user);
    },
    roleLockReason(user) {
      if (!user) return '';
      if (this.isSelf(user)) return 'You cannot change your own role.';
      if (this.isLastAdmin(user)) return 'At least one active admin is required.';
      return '';
    },
    statusTitle(user) {
      if (this.isSelf(user)) return 'You cannot disable your own account';
      if (this.isLastAdmin(user)) return 'The last active admin cannot be disabled';
      return user.is_active ? 'Enabled — click to disable sign-in' : 'Disabled — click to enable sign-in';
    },
    statusClass(user) {
      return ['inline-flex h-7 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-2 text-[11px] font-semibold disabled:cursor-not-allowed',
        user.is_active ? 'border-good/40 bg-good/10 text-good hover:enabled:bg-good/20' : 'border-edge-strong bg-raised text-ink-3 hover:enabled:text-ink'];
    },
    deleteTitle(user) {
      if (this.isSelf(user)) return 'You cannot delete your own account';
      if (this.isLastAdmin(user)) return 'The last active admin cannot be deleted';
      return 'Delete user';
    },
    isStatActive(stat) {
      if (stat.key === 'all') return this.roleFilter === 'all' && !this.quickFilter;
      return stat.key === 'admin' ? this.roleFilter === 'admin' : this.quickFilter === stat.key;
    },
    applyStat(stat) {
      if (stat.key === 'all') return this.resetFilters();
      if (stat.key === 'admin') this.roleFilter = this.roleFilter === 'admin' ? 'all' : 'admin';
      else this.quickFilter = this.quickFilter === stat.key ? '' : stat.key;
    },
    setViewMode(mode) {
      this.viewMode = mode;
      try { localStorage.setItem(VIEW_MODE_KEY, mode); } catch { /* storage unavailable */ }
    },
    mediaName(user) {
      const profile = this.mediaProfile(user);
      return profile?.external_username || profile?.external_user_id || '';
    },
    pagesSummary(user) {
      if (user.role === 'admin') return 'All pages';
      const count = this.userPages(user).length;
      return `${count} ${count === 1 ? 'page' : 'pages'}`;
    },
    pagesTitle(user) {
      return user.role === 'admin' ? 'Every page' : this.userPages(user).map(tab => tab.label).join(', ');
    },
    seerIdentity(user) {
      if (user.seer_user_id == null) return 'Technical user fallback';
      const seerUser = this.seerUsers.find(item => Number(item.id) === Number(user.seer_user_id));
      return seerUser?.displayName || seerUser?.username || seerUser?.email || `Seer user #${user.seer_user_id}`;
    },
    userPages(user) {
      const values = splitTabs(user.visible_tabs ?? DEFAULT_TABS).map(tab => this.normalizeTabValue(tab));
      return this.availableTabs.filter(tab => tab.required || values.includes(tab.value));
    },
    resetFilters() {
      this.userQuery = '';
      this.roleFilter = 'all';
      this.quickFilter = '';
    },
    normalizeTabValue(tabValue) {
      if (tabValue === 'suggestions') return 'requests';
      if (tabValue === 'ai-search') {
        return 'ai_search';
      }
      return tabValue;
    },

    async loadUsers() {
      this.isLoadingUsers = true;
      this.usersError = false;
      try {
        const res = await getUsers();
        this.users = res.data;
      } catch (err) {
        this.usersError = true;
        this.$toast.error('Failed to load users');
        console.error(err);
      } finally {
        this.isLoadingUsers = false;
      }
    },
    async loadSeerUsers() {
      try { this.seerUsers = (await axios.get('/api/seer/get_users')).data.users || []; }
      catch { this.seerUsers = []; }
    },

    async toggleActive(user) {
      this.isSaving[user.id] = true;
      const newActive = !user.is_active;
      try {
        await updateUser(user.id, { is_active: newActive });
        user.is_active = newActive;
        this.$toast.success(`${user.username} ${newActive ? 'activated' : 'deactivated'}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to update status');
        await this.loadUsers();
      } finally {
        this.isSaving[user.id] = false;
      }
    },

    openCreateModal() {
      this.newUser = { username: '', password: '', role: 'user' };
      this.createError = null;
      this.showNewPassword = false;
      this.showCreateModal = true;
    },

    async submitCreate() {
      this.createError = null;
      const { username, password, role } = this.newUser;
      if (!username.trim() || !password) {
        this.createError = 'Username and password are required.';
        return;
      }
      this.isCreating = true;
      try {
        await createUserAdmin({ username: username.trim(), password, role });
        this.$toast.success(`Account "${username.trim()}" created`);
        this.showCreateModal = false;
        await this.loadUsers();
      } catch (err) {
        this.createError = err.response?.data?.error || 'Failed to create account';
      } finally {
        this.isCreating = false;
      }
    },

    confirmDelete(user) {
      this.deleteTarget = user;
      this.showDeleteModal = true;
    },

    async submitDelete() {
      if (!this.deleteTarget) return;
      this.isDeleting = true;
      try {
        await deleteUser(this.deleteTarget.id);
        this.$toast.success(`Account "${this.deleteTarget.username}" deleted`);
        this.showDeleteModal = false;
        await this.loadUsers();
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to delete account');
      } finally {
        this.isDeleting = false;
        this.deleteTarget = null;
      }
    },

    openEditPermissionsModal(user) {
      const normalizedTabs = Array.isArray(user.visible_tabs)
        ? user.visible_tabs.map((t) => this.normalizeTabValue(t)).filter(Boolean)
        : user.visible_tabs
        ? user.visible_tabs.split(',').map((t) => this.normalizeTabValue(t.trim())).filter(Boolean)
        : [];

      if (!normalizedTabs.includes('profile')) {
        normalizedTabs.push('profile');
      }

      this.permissionsTarget = user;
      this.editPermissions = {
        role: user.role,
        can_manage_ai: user.can_manage_ai || false,
        visible_tabs_array: [...new Set(normalizedTabs)],
        seer_user_id: user.seer_user_id ?? null,
      };
      this.permissionsError = null;
      this.showPermissionsModal = true;
    },

    toggleTab(tabValue) {
      const tab = this.availableTabs.find((t) => t.value === tabValue);
      if (tab && tab.required) return; // Don't allow toggling required tabs

      const idx = this.editPermissions.visible_tabs_array.indexOf(tabValue);
      if (idx > -1) {
        this.editPermissions.visible_tabs_array.splice(idx, 1);
      } else {
        this.editPermissions.visible_tabs_array.push(tabValue);
      }
    },

    async submitPermissions() {
      if (!this.permissionsTarget) return;
      this.isSavingPermissions = true;
      this.permissionsError = null;
      try {
        const allowedTabs = [...new Set(
          this.editPermissions.visible_tabs_array
            .map((tab) => this.normalizeTabValue(tab))
            .filter(tab => this.availableTabs.some(available => available.value === tab))
        )];

        const payload = {
          can_manage_ai: this.editPermissions.can_manage_ai,
          allowed_tabs: allowedTabs,
          seer_user_id: this.editPermissions.seer_user_id == null ? null : Number(this.editPermissions.seer_user_id),
        };
        const avatarChanged = (this.permissionsTarget.seer_user_id ?? null) !== payload.seer_user_id;
        if (this.editPermissions.role !== this.permissionsTarget.role) {
          await updateUser(this.permissionsTarget.id, { role: this.editPermissions.role });
          this.permissionsTarget.role = this.editPermissions.role;
        }
        const response = await updateUserPermissions(this.permissionsTarget.id, payload);
        if (response?.data?.success !== true) {
          throw new Error('Unexpected permissions response');
        }
        this.$toast.success(`Permissions updated for ${this.permissionsTarget.username}`);
        this.showPermissionsModal = false;
        await this.loadUsers();
        if (avatarChanged) refreshUserAvatar(this.permissionsTarget.id);
      } catch (err) {
        console.error('Failed to update permissions:', err.response?.data || err);
        this.permissionsError = err.response?.data?.error || 'Failed to update permissions';
      } finally {
        this.isSavingPermissions = false;
      }
    },

    async openMediaLinkModal(user) {
      if (!this.supportsUserLinks) return;
      this.mediaLinkTarget = user;
      this.mediaUsers = [];
      this.selectedMediaUserId = String(this.mediaProfile(user)?.external_user_id || '');
      this.mediaLinkError = null;
      this.showMediaLinkModal = true;
      await this.loadMediaUsers();
    },

    async loadMediaUsers() {
      if (!this.supportsUserLinks) {
        this.mediaLinkError = 'No supported media service configured';
        return;
      }

      this.isLoadingMediaUsers = true;
      try {
        if (this.selectedService === 'plex') {
          const res = await fetchPlexUsers({
            PLEX_TOKEN: this.config.PLEX_TOKEN,
            PLEX_API_URL: this.config.PLEX_API_URL,
          });
          this.mediaUsers = res.data?.users || [];
        } else {
          const res = await getMediaServerUsers(this.selectedService);
          this.mediaUsers = Array.isArray(res.data) ? res.data : [];
        }
      } catch (err) {
        this.mediaUsers = [];
        this.mediaLinkError = err.response?.data?.error
          || err.response?.data?.message
          || `Failed to load ${this.providerLabel} users`;
      } finally {
        this.isLoadingMediaUsers = false;
      }
    },

    async submitMediaLink() {
      if (!this.mediaLinkTarget || !this.selectedMediaUser) return;
      this.isSavingMediaLink = true;
      this.mediaLinkError = null;
      try {
        const user = this.selectedMediaUser;
        const externalUsername = user.name || user.username || user.title || user.email || String(user.id);
        await adminLinkProvider(this.mediaLinkTarget.id, this.selectedService, {
          external_user_id: String(user.id),
          external_username: externalUsername,
        });
        this.$toast.success(`${this.providerLabel} account assigned to ${this.mediaLinkTarget.username}`);
        this.showMediaLinkModal = false;
        await this.loadUsers();
        refreshUserAvatar(this.mediaLinkTarget.id);
      } catch (err) {
        this.mediaLinkError = err.response?.data?.error || 'Failed to assign media account';
      } finally {
        this.isSavingMediaLink = false;
      }
    },

    async saveRegistration(changes) {
      const previous = { localAllowRegistration: this.localAllowRegistration, registrationTabs: this.registrationTabs };
      Object.assign(this, changes);
      this.isSavingRegistration = true;
      try {
        await axios.post('/api/config/section/advanced', {
          ALLOW_REGISTRATION: this.localAllowRegistration,
          REGISTRATION_DEFAULT_TABS: [...new Set([...this.registrationTabs, 'profile'])].join(','),
        });
        this.$toast.success('registrationTabs' in changes
          ? 'Pages for new accounts updated'
          : `Self-registration ${this.localAllowRegistration ? 'enabled' : 'disabled'}`);
      } catch {
        this.$toast.error('Failed to save registration setting');
        Object.assign(this, previous);
      } finally {
        this.isSavingRegistration = false;
      }
    },

    toggleRegistrationTab(value) {
      const tabs = this.registrationTabs.includes(value)
        ? this.registrationTabs.filter(tab => tab !== value)
        : [...this.registrationTabs, value];
      this.saveRegistration({ registrationTabs: tabs });
    },

    // The UI is English, so dates follow it instead of the browser locale.
    formatDate(ts, includeTime = true) {
      if (!ts) return 'Never';
      const date = new Date(ts);
      if (Number.isNaN(date.getTime())) return 'Not available';
      return date.toLocaleString('en', { dateStyle: 'medium', ...(includeTime ? { timeStyle: 'short' } : {}) });
    },

    relativeTime(ts) {
      const seconds = (new Date(ts).getTime() - Date.now()) / 1000;
      if (Number.isNaN(seconds)) return 'Not available';
      const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
      const [unit, size] = units.find(([, unitSize]) => Math.abs(seconds) >= unitSize) || ['second', 1];
      if (unit === 'second') return 'just now';
      return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(Math.round(seconds / size), unit);
    },
  },
};
</script>
