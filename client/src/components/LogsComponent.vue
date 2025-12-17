<template>
  <div class="logs-wrapper">
    <div class="filters-card">
      <div class="filter-group">
        <input 
          type="text" 
          v-model="filterText" 
          placeholder="Filter logs by message..." 
          class="filter-input" 
        />
      </div>

      <div class="filter-group">
        <BaseDropdown
          v-model="selectedSeverity"
          :options="severityOptions"
          placeholder="All Severities"
          id="severity-filter"
          class="severity-dropdown"
        />
      </div>

      <div class="filter-stats">
        <span class="stat-badge">
          <font-awesome-icon icon="list" />
          {{ filteredLogs.length }} 
          <template v-if="filteredLogs.length < allFilteredLogs.length">
            of {{ allFilteredLogs.length }}
          </template>
          rows
        </span>
        <button @click="toggleAutoUpdate" class="btn-toggle" :class="{ active: autoUpdate }">
          <font-awesome-icon :icon="autoUpdate ? 'pause' : 'play'" />
          <span>{{ autoUpdate ? 'Pause' : 'Resume' }}</span>
        </button>
      </div>
    </div>

    <div class="logs-table-card">
      <div class="table-scroll-container" @scroll="handleScroll">
        <table class="logs-table">
          <thead>
            <tr>
              <th class="col-timestamp">
                <font-awesome-icon icon="clock" />
                Timestamp
              </th>
              <th class="col-severity">
                <font-awesome-icon icon="exclamation-triangle" />
                Severity
              </th>
              <th class="col-label">
                <font-awesome-icon icon="tag" />
                Label
              </th>
              <th class="col-message">
                <font-awesome-icon icon="comment-alt" />
                Message
              </th>
              <th class="col-actions"></th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="(log, index) in filteredLogs" 
              :key="index"
              class="log-row"
              :class="`severity-${log.severity.toLowerCase()}`"
            >
              <td class="col-timestamp">
                <span class="timestamp-text">{{ formatTimestamp(log.dateTime) }}</span>
              </td>
              <td class="col-severity">
                <span :class="`severity-badge ${log.severity.toLowerCase()}`">
                  <font-awesome-icon :icon="getSeverityIcon(log.severity)" />
                  {{ log.severity }}
                </span>
              </td>
              <td class="col-label">
                <span class="label-text">{{ log.tag }}</span>
              </td>
              <td class="col-message">
                <span class="message-text">{{ log.message }}</span>
              </td>
              <td class="col-actions">
                <button @click="copyLog(log)" class="btn-copy" title="Copy log">
                  <font-awesome-icon icon="copy" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="loadingMore" class="loading-state">
          <div class="spinner"></div>
          <p>Loading more logs...</p>
        </div>

        <div v-if="filteredLogs.length === 0" class="empty-state">
          <font-awesome-icon icon="inbox" />
          <p>No logs found</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import '@/assets/styles/logs.css';
import axios from 'axios';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { 
  faPlay, faPause, faFileAlt, faSearch, faFilter, 
  faList, faClock, faExclamationTriangle, faTag, 
  faCommentAlt, faCopy, faInbox, faCheckCircle,
  faInfoCircle, faExclamationCircle, faBug
} from '@fortawesome/free-solid-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  components: {
    FontAwesomeIcon,
    BaseDropdown
  },
  data() {
    return {
      logs: [],
      displayedLogs: [],
      filteredDisplayedLogs: [],
      filterText: '',
      selectedSeverity: '',
      autoUpdate: true,
      updateInterval: null,
      batchSize: 100,
      loadingMore: false,
      severityOptions: [
        { value: '', label: 'All Severities' },
        { value: 'DEBUG', label: 'DEBUG' },
        { value: 'INFO', label: 'INFO' },
        { value: 'WARNING', label: 'WARNING' },
        { value: 'ERROR', label: 'ERROR' }
      ]
    };
  },
  computed: {
    filteredLogs() {
      const severity = (this.selectedSeverity === 'All Severities' || !this.selectedSeverity) ? '' : this.selectedSeverity;
      const hasFilter = this.filterText.trim() !== '' || severity !== '';

      if (!hasFilter) {
        return this.displayedLogs;
      }

      return this.filteredDisplayedLogs;
    },
    allFilteredLogs() {
      const severity = (this.selectedSeverity === 'All Severities' || !this.selectedSeverity) ? '' : this.selectedSeverity;
      const hasFilter = this.filterText.trim() !== '' || severity !== '';

      if (!hasFilter) {
        return this.logs;
      }

      return this.logs.filter(log => {
        const matchesText = !this.filterText || 
          (log.message && log.message.toLowerCase().includes(this.filterText.toLowerCase()));
        const matchesSeverity = !severity || log.severity === severity;
        return matchesText && matchesSeverity;
      });
    }
  },
  watch: {
    selectedSeverity(newVal, oldVal) {

      if (newVal === 'All Severities') {
        this.selectedSeverity = '';
        return;
      }

      this.applyFilters();

      if (oldVal && (!newVal || newVal === '') && !this.filterText) {
        this.displayedLogs = this.logs.slice(0, this.batchSize);
      }
    },
    filterText(newVal, oldVal) {
      this.applyFilters();
      if (oldVal && !newVal && (!this.selectedSeverity || this.selectedSeverity === '')) {
        this.displayedLogs = this.logs.slice(0, this.batchSize);
      }
    }
  },
  mounted() {
    this.startAutoUpdate();
    const container = this.$el.querySelector('.table-scroll-container');
    if (container) {
      container.addEventListener('scroll', this.handleScroll);
    }
  },
  beforeUnmount() {
    this.stopAutoUpdate();
    const container = this.$el.querySelector('.table-scroll-container');
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
    }
  },
  methods: {
    applyFilters() {
      const severity = (this.selectedSeverity === 'All Severities' || !this.selectedSeverity) ? '' : this.selectedSeverity;
      const hasFilter = this.filterText.trim() !== '' || severity !== '';
      
      if (hasFilter) {
        const filtered = this.logs.filter(log => {
          const matchesText = !this.filterText || 
            (log.message && log.message.toLowerCase().includes(this.filterText.toLowerCase()));
          const matchesSeverity = !severity || log.severity === severity;
          return matchesText && matchesSeverity;
        });

        this.filteredDisplayedLogs = filtered.slice(0, this.batchSize);
      }
    },
    fetchLogs() {
      axios.get('/api/logs')
        .then(response => {
          this.logs = this.parseLogs(response.data).reverse();
          if (!this.filterText && !this.selectedSeverity) {
            this.displayedLogs = this.logs.slice(0, this.batchSize);
          }
        })
        .catch(error => {
          console.error('Error fetching logs:', error);
        });
    },
    loadMoreLogs() {
      const severity = (this.selectedSeverity === 'All Severities' || !this.selectedSeverity) ? '' : this.selectedSeverity;
      const hasFilter = this.filterText.trim() !== '' || severity !== '';

      if (this.loadingMore) return;

      this.loadingMore = true;

      setTimeout(() => {
        if (!hasFilter) {
          if (this.displayedLogs.length >= this.logs.length) {
            this.loadingMore = false;
            return;
          }

          const nextBatch = this.logs.slice(
            this.displayedLogs.length,
            this.displayedLogs.length + this.batchSize
          );
          this.displayedLogs = [...this.displayedLogs, ...nextBatch];
        } else {
          if (this.filteredDisplayedLogs.length >= this.allFilteredLogs.length) {
            this.loadingMore = false;
            return;
          }

          const nextBatch = this.allFilteredLogs.slice(
            this.filteredDisplayedLogs.length,
            this.filteredDisplayedLogs.length + this.batchSize
          );
          this.filteredDisplayedLogs = [...this.filteredDisplayedLogs, ...nextBatch];
        }

        this.loadingMore = false;
      }, 500);
    },
    handleScroll() {
      const container = this.$el.querySelector('.table-scroll-container');
      if (!container) return;
    
      const scrollPosition = container.scrollTop + container.clientHeight;
      const bottomPosition = container.scrollHeight;
      
      const severity = (this.selectedSeverity === 'All Severities' || !this.selectedSeverity) ? '' : this.selectedSeverity;
      const hasFilter = this.filterText.trim() !== '' || severity !== '';
      
      const currentLength = hasFilter ? this.filteredDisplayedLogs.length : this.displayedLogs.length;
      const totalLength = hasFilter ? this.allFilteredLogs.length : this.logs.length;
    
      if (scrollPosition >= bottomPosition * 0.9 && currentLength < totalLength) {
        this.loadMoreLogs();
      }
    },
    parseLogs(logData) {
      return logData
        .map(logLine => {
          const parts = logLine.split(' - ');
          if (parts.length < 4) return null;
          
          const [dateTime, tag, severity, ...messageParts] = parts;
          const message = messageParts.join(' - ');
          
          return { 
            dateTime: dateTime.trim(), 
            tag: tag.trim(), 
            severity: severity.trim(), 
            message: message.trim() 
          };
        })
        .filter(log => log !== null && log.message && log.message.trim() !== '');
    },
    formatTimestamp(timestamp) {
      if (!timestamp) return 'N/A';
      return timestamp;
    },
    getSeverityIcon(severity) {
      const icons = {
        'DEBUG': 'bug',
        'INFO': 'info-circle',
        'WARNING': 'exclamation-triangle',
        'ERROR': 'exclamation-circle'
      };
      return icons[severity] || 'info-circle';
    },
    copyLog(log) {
      const logText = `${log.dateTime} - ${log.tag} - ${log.severity} - ${log.message}`;
      navigator.clipboard.writeText(logText)
        .then(() => {
          this.$toast.open({
            message: 'Log copied to clipboard!',
            type: 'success',
            duration: 5000,
            position: 'top-right'
          });
        })
        .catch(err => {
          console.error('Error while copying log:', err);
        });
    },
    startAutoUpdate() {
      this.fetchLogs();
      this.updateInterval = setInterval(this.fetchLogs, 5000);
      this.autoUpdate = true;
    },
    stopAutoUpdate() {
      if (this.updateInterval) {
        clearInterval(this.updateInterval);
        this.updateInterval = null;
        this.autoUpdate = false;
      }
    },
    toggleAutoUpdate() {
      if (this.autoUpdate) {
        this.stopAutoUpdate();
      } else {
        this.startAutoUpdate();
      }
    }
  },
  created() {
    library.add(
      faPlay, faPause, faFileAlt, faSearch, faFilter, 
      faList, faClock, faExclamationTriangle, faTag, 
      faCommentAlt, faCopy, faInbox, faCheckCircle,
      faInfoCircle, faExclamationCircle, faBug
    );
  }
};
</script>