<template>
  <div class="config-section">
    <h3 class="section-title">{{ serviceName }} Configuration</h3>
    <p class="section-description">
      Connect to your {{ serviceName }} server to import libraries and user preferences.
    </p>

    <!-- Server URL Input -->
    <div class="form-group">
      <label :for="`JELLYFIN_API_URL`" class="form-label">
        {{ serviceName }} Server URL
      </label>
      <input 
        type="url" 
        :value="config[`JELLYFIN_API_URL`]" 
        @input="handleUrlInput($event.target.value)"
        @blur="updateApiUrl($event.target.value)"
        class="form-input"
        :placeholder="`http://your-${serviceName.toLowerCase()}-server:8096`"
      >
      <p class="form-help">
        <i class="fas fa-info-circle"></i> 
        Example: http://192.168.1.100:8096 or https://{{ serviceName.toLowerCase() }}.example.com
      </p>
    </div>

    <!-- API Key Input with Test Button -->
    <div class="form-group">
      <label :for="`JELLYFIN_TOKEN`" class="form-label">
        {{ serviceName }} API Key
      </label>
      <div class="input-group">
        <input 
          type="password" 
          :value="config[`JELLYFIN_TOKEN`]"
          @input="handleTokenInput($event.target.value)"
          :disabled="testState.isTesting"
          class="form-input"
          :placeholder="`Your ${serviceName} API Key`"
        >
        
        <button 
          type="button" 
          @click="fetchLibraries" 
          :disabled="testState.isTesting || !canTest"
          :class="[
            'btn btn-test',
            {
              'btn-success': testState.status === 'success',
              'btn-danger': testState.status === 'fail',
              'btn-primary': testState.status === null && canTest,
              'btn-disabled': !canTest
            }
          ]"
        >
          <span v-if="testState.isTesting" class="btn-content">
            <i class="fas fa-spinner fa-spin"></i>
            <span class="btn-text">Testing</span>
          </span>
          <span v-else-if="testState.status === 'success'" class="btn-content">
            <i class="fas fa-check"></i>
            <span class="btn-text">Connected</span>
          </span>
          <span v-else-if="testState.status === 'fail'" class="btn-content">
            <i class="fas fa-times"></i>
            <span class="btn-text">Failed</span>
          </span>
          <span v-else class="btn-content">
            <i class="fas fa-plug"></i>
            <span class="btn-text">Connect</span>
          </span>
        </button>
      </div>
      
      <div class="help-section">
        <button 
          type="button"
          @click="showApiKeyHelp = !showApiKeyHelp"
          class="help-link">
          <i class="fas fa-question-circle"></i>
          How to get your API Key?
        </button>
        
        <div v-if="showApiKeyHelp" class="help-content">
          <ol class="help-list">
            <li>Open {{ serviceName }} web interface</li>
            <li>Navigate to Dashboard → API Keys</li>
            <li>Click "New API Key" and give it a name</li>
            <li>Copy the generated key and paste it above</li>
          </ol>
        </div>
      </div>
    </div>

    <!-- Success Message -->
    <div v-if="testState.status === 'success'" 
         class="alert alert-success" 
         role="alert">
      <i class="fas fa-check-circle"></i>
      <span>Successfully connected to {{ serviceName }}! Found {{ libraries.length }} libraries and {{ users.length }} users.</span>
    </div>

    <!-- Error Message -->
    <div v-if="testState.status === 'fail'"
         class="alert alert-danger" 
         role="alert">
      <i class="fas fa-exclamation-circle"></i>
      <span>Failed to connect to {{ serviceName }}. Please verify your URL and API Key.</span>
    </div>

    <!-- Libraries Selection -->
    <div v-if="libraries.length > 0" class="selection-group">
      <div class="selection-header">
        <div class="selection-info">
          <h4 class="selection-title">Select Libraries</h4>
          <p class="selection-subtitle">
            {{ selectedLibraryIds.length > 0 ? `${selectedLibraryIds.length} selected` : 'Select libraries or leave empty for all' }}
          </p>
        </div>
        <button 
          v-if="selectedLibraryIds.length > 0"
          @click="clearLibrarySelection"
          class="clear-btn">
          <i class="fas fa-times-circle"></i>
          Clear Selection
        </button>
      </div>
      
      <div class="selection-grid">
        <div 
          v-for="library in libraries" 
          :key="library.ItemId" 
          @click="toggleLibrarySelection(library)"
          :class="['selection-item', { 'selected': isSelected(library.ItemId) }]"
        >
          <!-- Checkmark for selected items -->
          <div v-if="isSelected(library.ItemId)" class="selection-check">
            <i class="fas fa-check"></i>
          </div>
          
          <!-- Library icon based on type -->
          <i :class="getLibraryIcon(library.CollectionType)" class="selection-icon"></i>
          
          <p class="selection-name">{{ library.Name }}</p>
        </div>
      </div>
    </div>

    <!-- Users Selection -->
    <div v-if="users.length > 0" class="selection-group">
      <div class="selection-header">
        <div class="selection-info">
          <h4 class="selection-title">Select Users</h4>
          <p class="selection-subtitle">
            {{ selectedUserIds.length > 0 ? `${selectedUserIds.length} selected` : 'Select users or leave empty for all' }}
          </p>
        </div>
        <button 
          v-if="selectedUserIds.length > 0"
          @click="clearUserSelection"
          class="clear-btn">
          <i class="fas fa-times-circle"></i>
          Clear Selection
        </button>
      </div>
      
      <div class="selection-grid users-grid">
        <div 
          v-for="user in users" 
          :key="user.id" 
          @click="toggleUserSelection(user)"
          :class="['selection-item', { 'selected': isUserSelected(user.id) }]"
        >
          <div v-if="isUserSelected(user.id)" class="selection-check">
            <i class="fas fa-check"></i>
          </div>
          
          <i class="fas fa-user-circle selection-icon"></i>
          <p class="selection-name">{{ user.name }}</p>
        </div>
      </div>
    </div>

    <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button @click="$emit('previous-step')"
                    class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full 
                           transition-colors duration-200">
                <i class="fas fa-arrow-left mr-2"></i>Back
            </button>
            <button @click="$emit('next-step')"
                    :disabled="!config.SELECTED_SERVICE"
                    class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full
                           transition-colors duration-200"
                    :class="{ 'opacity-50 cursor-not-allowed': !config.SELECTED_SERVICE }">
                Next Step<i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
  </div>
</template>

<style scoped>
/* Config Section */
.config-section {
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.section-description {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1rem;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary);
  transition: all 0.2s ease;
}

.link:hover {
  color: var(--color-primary-hover);
  border-bottom-style: solid;
}

/* Form Elements */
.form-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.form-input {
  flex: 1;
  min-width: 200px;
  min-height: 40px;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  padding: 0 1rem;
  color: var(--color-text-primary);
  font-size: 0.9rem;
  transition: var(--transition-base);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-input::placeholder {
  color: var(--color-text-muted);
}

/* Buttons */
.btn-test {
  min-width: 100px;
  height: 44px;
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
  white-space: nowrap;
  background-color: grey;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-text {
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-success {
  background: var(--color-success);
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #218838;
}

.btn-danger {
  background: var(--color-danger);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn-secondary {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 2px solid var(--color-border-medium);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg-active);
  border-color: var(--color-border-medium);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Alerts */
.alert {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: var(--border-radius-sm);
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}

/* Navigation */
.navigation-buttons {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2rem;
}

.navigation-buttons .btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
  white-space: nowrap;
}

.navigation-buttons .btn:first-child {
  justify-self: flex-start;
}

.navigation-buttons .btn:last-child {
  justify-self: flex-end;
}

/* Form Groups */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.form-help {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Help Section */
.help-section {
  margin-top: 0.5rem;
}

.help-link {
  background: none;
  border: none;
  color: #ececf985;
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition-base);
  padding: 0.25rem 0;
}

.help-link:hover {
  color: var(--color-primary-hover);
}

.help-content {
  margin-top: 0.75rem;
  padding: 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
}

.help-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  counter-reset: list-counter;
}

.help-list li {
  color: var(--color-text-secondary);
  font-size: 0.85rem;
  padding-left: 1.5rem;
  position: relative;
}

.help-list li::before {
  counter-increment: list-counter;
  content: counter(list-counter) ".";
  position: absolute;
  left: 0;
  color: var(--color-primary);
  font-weight: 600;
}

/* Selection Groups */
.selection-group {
  margin-bottom: 1.5rem;
}

.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.selection-info {
  flex: 1;
}

.selection-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 0.25rem 0;
}

.selection-subtitle {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin: 0;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition-base);
  padding: 0.25rem 0.5rem;
  border-radius: var(--border-radius-sm);
}

.clear-btn:hover {
  color: var(--color-primary-hover);
  background: var(--color-bg-interactive);
}

/* Selection Grid */
.selection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.users-grid {
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
}

.selection-item {
  cursor: pointer;
  padding: 1rem;
  border: 2px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  text-align: center;
  color: var(--color-text-primary);
  transition: var(--transition-base);
  position: relative;
  background: var(--color-bg-interactive);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.selection-item:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.selection-item.selected {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.selection-check {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: white;
  color: var(--color-primary);
  border-radius: 50%;
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.selection-icon {
  font-size: 1.5rem;
  opacity: 0.8;
}

.selection-item.selected .selection-icon {
  opacity: 1;
}

.selection-name {
  font-weight: 500;
  font-size: 0.9rem;
  margin: 0;
  line-height: 1.2;
}

/* Responsive */
@media (max-width: 768px) {
  .input-group {
    flex-direction: column;
    align-items: stretch;
  }

  .form-input {
    min-width: auto;
  }

  .btn-test {
    min-width: auto;
  }

  .navigation-buttons {
    flex-direction: column;
    gap: 0.75rem;
  }

  .navigation-buttons .btn {
    width: 100%;
    justify-content: center;
    min-height: 48px;
  }

  .btn-text {
    display: none;
  }

  .section-description {
    font-size: 0.85rem;
  }

  .selection-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .users-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .selection-item {
    padding: 0.75rem;
  }

  .selection-header {
    flex-direction: column;
    align-items: stretch;
  }

  .clear-btn {
    align-self: flex-start;
  }
}

/* Form Groups */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.form-help {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Help Section */
.help-section {
  margin-top: 0.5rem;
}

.help-link {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition-base);
  padding: 0.25rem 0;
}

.help-link:hover {
  color: var(--color-primary-hover);
}

.help-content {
  margin-top: 0.75rem;
  padding: 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
}

.help-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.help-list li {
  color: var(--color-text-secondary);
  font-size: 0.85rem;
  padding-left: 1.5rem;
  position: relative;
}

.help-list li::before {
  content: counter(list-item) ".";
  position: absolute;
  left: 0;
  color: var(--color-primary);
  font-weight: 600;
}

/* Selection Groups */
.selection-group {
  margin-bottom: 1.5rem;
}

.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.selection-info {
  flex: 1;
}

.selection-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 0.25rem 0;
}

.selection-subtitle {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin: 0;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition-base);
  padding: 0.25rem 0.5rem;
  border-radius: var(--border-radius-sm);
}

.clear-btn:hover {
  color: var(--color-primary-hover);
  background: var(--color-bg-interactive);
}

/* Selection Grid */
.selection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.users-grid {
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
}

.selection-item {
  cursor: pointer;
  padding: 1rem;
  border: 2px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  text-align: center;
  color: var(--color-text-primary);
  transition: var(--transition-base);
  position: relative;
  background: var(--color-bg-interactive);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.selection-item:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.selection-item.selected {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.selection-check {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: white;
  color: var(--color-primary);
  border-radius: 50%;
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.selection-icon {
  font-size: 1.5rem;
  opacity: 0.8;
}

.selection-item.selected .selection-icon {
  opacity: 1;
}

.selection-name {
  font-weight: 500;
  font-size: 0.9rem;
  margin: 0;
  line-height: 1.2;
}

/* Responsive */
@media (max-width: 768px) {
  .selection-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .users-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .selection-item {
    padding: 0.75rem;
  }

  .selection-header {
    flex-direction: column;
    align-items: stretch;
  }

  .clear-btn {
    align-self: flex-start;
  }
}
</style>

<script>
import { fetchJellyfinLibraries, fetchJellyfinUsers } from '../../api/api';

export default {
  props: ['config'],
  data() {
    return {
      testState: {
        status: null,
        isTesting: false
      },
      libraries: [],
      selectedLibraryIds: [],
      selectedLibraryNames: [],
      users: [],
      selectedUserIds: [],
      selectedUserName: [],
      showApiKeyHelp: false,
    };
  },
    computed: {
        serviceName() {
            return this.config.SELECTED_SERVICE === 'emby' ? 'Emby' : 'Jellyfin';
        },
        canTest() {
            return this.config[`JELLYFIN_API_URL`] && this.config[`JELLYFIN_TOKEN`];
        },
        canProceed() {
            return this.testState.status === 'success';
        }
    },
    methods: {
        handleUrlInput(value) {
            // Reset test state when URL changes
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.libraries = [];
                this.users = [];
            }
        },
        
        handleTokenInput(value) {
            this.$emit('update-config', `JELLYFIN_TOKEN`, value);
            // Reset test state when token changes
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.libraries = [];
                this.users = [];
            }
        },

        fetchLibraries() {
            if (!this.canTest) return;
            
            this.testState.isTesting = true;
            this.testState.status = null;
            
            fetchJellyfinLibraries(this.config[`JELLYFIN_API_URL`], this.config[`JELLYFIN_TOKEN`])
                .then(response => {
                    this.libraries = response.data.items;
                    this.testState.status = 'success';
                    this.loadSelectedLibraries();
                    this.fetchUsers();
                })
                .catch(error => {
                    console.error('Error fetching libraries:', error);
                    this.testState.status = 'fail';
                    this.libraries = [];
                    this.users = [];
                })
                .finally(() => {
                    this.testState.isTesting = false;
                });
        },

        fetchUsers() {
            fetchJellyfinUsers(this.config[`JELLYFIN_API_URL`], this.config[`JELLYFIN_TOKEN`])
                .then(response => {
                    this.users = response.data.users;
                    this.loadSelectedUsers();
                })
                .catch(error => {
                    console.error('Error fetching users:', error);
                });
        },

        toggleLibrarySelection(library) {
            const index = this.selectedLibraryIds.indexOf(library.ItemId);
            if (index === -1) {
                this.selectedLibraryIds.push(library.ItemId);
                this.selectedLibraryNames.push(library.Name);
            } else {
                this.selectedLibraryIds.splice(index, 1);
                this.selectedLibraryNames.splice(this.selectedLibraryNames.indexOf(library.Name), 1);
            }
            this.$emit('update-config', `JELLYFIN_LIBRARIES`, this.combineLibraryData(this.selectedLibraryIds, this.selectedLibraryNames));
        },

        toggleUserSelection(user) {
            const index = this.selectedUserIds.indexOf(user.id);
            if (index === -1) {
                this.selectedUserIds.push(user.id);
                this.selectedUserName.push(user.name);
            } else {
                this.selectedUserIds.splice(index, 1);
                this.selectedUserName.splice(index, 1);
            }
        
            const cleanedIds = this.selectedUserIds.filter(id => id);
            const cleanedNames = this.selectedUserName.filter(name => name);
            const cleanSelectedUsers = this.combineLibraryData(cleanedIds, cleanedNames);
        
            this.$emit('update-config', `SELECTED_USERS`, cleanSelectedUsers);
        },

        clearLibrarySelection() {
            this.selectedLibraryIds = [];
            this.selectedLibraryNames = [];
            this.$emit('update-config', `JELLYFIN_LIBRARIES`, []);
        },

        clearUserSelection() {
            this.selectedUserIds = [];
            this.selectedUserName = [];
            this.$emit('update-config', `SELECTED_USERS`, []);
        },

        isUserSelected(userId) {
            return this.selectedUserIds.includes(userId);
        },

        isSelected(libraryId) {
            return this.selectedLibraryIds.includes(libraryId);
        },

        getLibraryIcon(collectionType) {
            const icons = {
                'movies': 'fas fa-film',
                'tvshows': 'fas fa-tv',
                'music': 'fas fa-music',
                'books': 'fas fa-book',
                'photos': 'fas fa-images'
            };
            return icons[collectionType?.toLowerCase()] || 'fas fa-folder';
        },

        loadSelectedLibraries() {
            if (this.config[`JELLYFIN_LIBRARIES`]) {
                this.selectedLibraryIds = this.config[`JELLYFIN_LIBRARIES`].map(lib => lib.id);
                this.selectedLibraryNames = this.config[`JELLYFIN_LIBRARIES`].map(lib => lib.name);
            }
        },

        loadSelectedUsers() {
            if (this.config[`SELECTED_USERS`]) {
                this.selectedUserIds = this.config[`SELECTED_USERS`].map(user => user.id);
                this.selectedUserName = this.config[`SELECTED_USERS`].map(user => user.name);
            }
        },

        combineLibraryData(ids, names) {
            if (ids.length !== names.length) {
                console.error("Mismatch between number of ids and names");
                return [];
            }

            return ids
                .map((id, index) => ({ id: id, name: names[index] }))
                .filter(item => item.id && item.name);
        },

        updateApiUrl(url) {
            const trimmedUrl = url.trim().replace(/\/+$/, ''); // Remove trailing slashes
            this.$emit('update-config', `JELLYFIN_API_URL`, trimmedUrl);
        },

        handleNext() {
            if (this.canProceed) {
                this.$emit('next-step');
            }
        },

        autoTestService() {
            if (this.canTest) {
                this.fetchLibraries();
            }
        }
    },
    mounted() {
        this.autoTestService();
    }
};
</script>
