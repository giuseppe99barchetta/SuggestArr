<template>
  <div class="logs-container">
    <div class="logs-table-container">

      <div class="filter-container">
        <input type="text" v-model="filterText" placeholder="Filter logs..." class="filter-input" />

        <select v-model="selectedSeverity" class="severity-dropdown">
          <option value="">All Severities</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>

        <button @click="toggleAutoUpdate" class="toggle-button">
          <font-awesome-icon :icon="[autoUpdate ? 'fas' : 'fas', autoUpdate ? 'pause' : 'play']" />
        </button>

      </div>

      <table class="logs-table">
        <thead>
          <tr>
            <th>TIMESTAMP</th>
            <th>SEVERITY</th>
            <th>LABEL</th>
            <th>MESSAGE</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(log, index) in filteredLogs" :key="index">
            <td>{{ log.dateTime }}</td>
            <td><span :class="`severity-label ${log.severity.toLowerCase()}`">{{ log.severity }}</span></td>
            <td>{{ log.tag }}</td>
            <td>{{ log.message }}</td>
            <td>
              <button @click="copyLog(log)" class="copy-button">Copy</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="loadingMore" class="loading-spinner">
            <font-awesome-icon icon="spinner" spin />
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faPlay, faPause, faSpinner } from '@fortawesome/free-solid-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';

export default {
  components: {
    FontAwesomeIcon
  },
  data() {
    return {
      logs: [],
      displayedLogs: [], 
      filterText: '',
      selectedSeverity: '',
      autoUpdate: true,
      updateInterval: null,
      batchSize: 100,
      loadingMore: false,
    };
  },
  computed: {
    filteredLogs() {
      const logsToFilter = this.filterText || this.selectedSeverity ? this.logs : this.displayedLogs;

      return logsToFilter.filter(log => {
        const matchesText = log.message && log.message.toLowerCase().includes(this.filterText.toLowerCase());
        const matchesSeverity = this.selectedSeverity === '' || log.severity === this.selectedSeverity;
        return matchesText && matchesSeverity;
      });
    }
  },
  mounted() {
    this.startAutoUpdate();
    const container = this.$el.querySelector('.logs-table-container');
    container.addEventListener('scroll', this.handleScroll);
  },
  beforeUnmount() {
    this.stopAutoUpdate();
    const container = this.$el.querySelector('.logs-table-container');
    container.removeEventListener('scroll', this.handleScroll);
  },
  methods: {
    fetchLogs() {
      axios.get('/api/logs')
        .then(response => {
          this.logs = this.parseLogs(response.data).reverse();
          this.displayedLogs = this.logs.slice(0, this.batchSize)
        })
        .catch(error => {
          console.error('Error fetching logs:', error);
        });
    },
    loadMoreLogs() {
      const logsToLoadFrom = this.selectedSeverity || this.filterText ? this.filteredLogs : this.logs;
      if (this.loadingMore || this.displayedLogs.length >= logsToLoadFrom.length) return;

      this.loadingMore = true;
      setTimeout(() => {
        const nextBatch = this.logs.slice(
          this.displayedLogs.length,
          this.displayedLogs.length + this.batchSize
        );
        this.displayedLogs = [...this.displayedLogs, ...nextBatch];
        this.loadingMore = false;
      }, 500);
    },
    handleScroll() {
      const container = this.$el.querySelector('.logs-table-container');
      const scrollPosition = container.scrollTop + container.clientHeight;
      const bottomPosition = container.scrollHeight;
      const logsToLoadFrom = this.selectedSeverity || this.filterText ? this.filteredLogs : this.logs;

      if (scrollPosition >= bottomPosition * 0.9 && this.displayedLogs.length < logsToLoadFrom.length) {
        this.loadMoreLogs();
      }
    },
    parseLogs(logData) {
      return logData.map(logLine => {
        const [dateTime, tag, severity, message] = logLine.split(' - ');
        return { dateTime, tag, severity, message };
      });
    },
    copyLog(log) {
      const logText = `${log.dateTime} - ${log.tag} - ${log.severity} - ${log.message}`;
      navigator.clipboard.writeText(logText)
        .then(() => {
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
    library.add(faPlay, faPause, faSpinner);
  }
};
</script>

<style scoped>
.logs-container {
  margin: 5px;
}

.logs-table-container {
  overflow-x: auto;
  background-color: #111827;
  border-radius: 8px;
  border: 1px solid #374151;
}

.logs-table {
  width: 100%;
  border-collapse: collapse;
}

.logs-table th,
.logs-table td {
  padding: 10px 15px;
  text-align: left;
  color: #d1d5db;
  font-size: 14px;
}

.logs-table th {
  background-color: #1f2937;
  color: #9ca3af;
  border-bottom: 1px solid #374151;
}

.logs-table tr:nth-child(even) {
  background-color: #1f2937;
}

.logs-table tr:nth-child(odd) {
  background-color: #2d3748;
}

.severity-label {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: bold;
  min-width: 100%;
  text-align: center;
}

.severity-label.debug {
  background-color: #3b82f6;
  color: #fff;
}

.severity-label.info {
  background-color: #10b981;
  color: #fff;
}

.severity-label.warning {
  background-color: #ffcc00;
  color: #fff;
}

.severity-label.error {
  background-color: #ef4444;
  color: #fff;
}

.copy-button {
  background-color: #3b82f6;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 5px;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.copy-button:hover {
  background-color: #2563eb;
}

.logs-table-container {
  overflow-x: auto;
  overflow-y: scroll;
  max-height: 500px;
  background-color: #111827;
  border-radius: 8px;
  border: 1px solid #374151;
}

.logs-table-container {
  overflow-x: auto;
  overflow-y: scroll;
  max-height: 400px;
  background-color: #111827;
  border-radius: 8px;
  border: 1px solid #374151;
}

.logs-table-container::-webkit-scrollbar {
  width: 10px;
}

.logs-table-container::-webkit-scrollbar-track {
  background: #1f2937;
}

.logs-table-container::-webkit-scrollbar-thumb {
  background-color: #3b82f6;
  border-radius: 10px;
  border: 2px solid #1f2937;
}

.logs-table-container::-webkit-scrollbar-thumb:hover {
  background-color: #2563eb;
}

.filter-container {
  display: flex;
  gap: 10px;
  margin: 10px;
}

.filter-input {
  padding: 8px;
  border: 1px solid #374151;
  border-radius: 4px;
  background-color: #1f2937;
  color: white;
  width: 70%;
}

.severity-dropdown {
  padding: 8px;
  border: 1px solid #374151;
  border-radius: 4px;
  background-color: #1f2937;
  color: white;
  width: 30%;
}

.loading-spinner {
  text-align: center;
  margin: 10px 0;
  color: #3b82f6;
}

</style>
