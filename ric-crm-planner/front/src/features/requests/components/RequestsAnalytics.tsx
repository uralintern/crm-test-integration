import { Progress, Segmented, Tooltip } from "antd";
import { DownOutlined, SettingFilled } from "@ant-design/icons";
import AppButton from "../../../components/UI/Button";
import { ORGANIZER_REQUEST_STATUSES } from "../../../constants/requestProgress";
import {
  DASHBOARD_START_ANGLE,
  DASHBOARD_SWEEP_ANGLE,
  OTHER_STATUS_COLOR,
  OTHER_STATUS_KEY,
  REQUESTS_TEXT as TEXT,
  REQUEST_STATUS_COLORS,
} from "../config/requestsConfig";
import type { AnalyticsStatus, AnalyticsStatusKey, RequestsChartView } from "../types";
import { getArcPath, getStatusSegmentPath } from "../utils/requestsUtils";

type RequestsAnalyticsProps = {
  chartView: RequestsChartView;
  onChartViewChange: (value: RequestsChartView) => void;
  onOpenStatusSettings: () => void;
  analyticsStatuses: AnalyticsStatus[];
  totalRequests: number;
  expandedStatusKeys: AnalyticsStatusKey[];
  onToggleStatusList: (statusKey: AnalyticsStatusKey) => void;
};

export function RequestsAnalytics({
  chartView,
  onChartViewChange,
  onOpenStatusSettings,
  analyticsStatuses,
  totalRequests,
  expandedStatusKeys,
  onToggleStatusList,
}: RequestsAnalyticsProps) {
  const percentOfTotal = (count: number) => (totalRequests > 0 ? Math.round((count / totalRequests) * 100) : 0);
  const statusSegments = analyticsStatuses.map((item) => ({
    ...item,
    percent: totalRequests > 0 ? (item.count / totalRequests) * 100 : 0,
    roundedPercent: percentOfTotal(item.count),
  }));
  const visibleStatusSegments = statusSegments.filter((item) => item.count > 0);
  const dashboardSegments = visibleStatusSegments.reduce<{
    accumulatedPercent: number;
    segments: Array<(typeof visibleStatusSegments)[number] & { path: string }>;
  }>(
    (acc, item, index) => ({
      accumulatedPercent: acc.accumulatedPercent + item.percent,
      segments: [
        ...acc.segments,
        {
          ...item,
          path: getStatusSegmentPath(index, item.percent, acc.accumulatedPercent),
        },
      ],
    }),
    { accumulatedPercent: 0, segments: [] }
  ).segments;

  return (
    <section className="requests-analytics">
      <div className={`requests-analytics__hero requests-analytics__hero--${chartView}`}>
        <div className="requests-analytics__copy">
          <h2>{TEXT.requestsDiagram}</h2>
          <p>{TEXT.distribution}</p>
          <Segmented
            className="requests-chart-toggle"
            size="large"
            shape="round"
            value={chartView}
            onChange={(value) => onChartViewChange(value as RequestsChartView)}
            options={[
              { label: TEXT.circleDiagram, value: "circle" },
              { label: TEXT.lineDiagram, value: "line" },
            ]}
          />
          <AppButton className="requests-status-settings-btn" onClick={onOpenStatusSettings}>
            <SettingFilled />
            <span>{TEXT.statusDisplaySettings}</span>
          </AppButton>
        </div>

        {chartView === "circle" ? (
          <div className="requests-analytics__dashboard">
            <div className="requests-analytics__dashboard-chart">
              <svg className="requests-analytics__dashboard-svg" viewBox="0 0 200 170" aria-label={TEXT.requestsDiagram}>
                <path
                  className="requests-analytics__dashboard-trail"
                  d={getArcPath(DASHBOARD_START_ANGLE, DASHBOARD_START_ANGLE + DASHBOARD_SWEEP_ANGLE)}
                />
                {dashboardSegments.map((item) => (
                  <Tooltip key={item.key} title={`${item.label}: ${item.count} ${TEXT.total}, ${item.roundedPercent}% ${TEXT.percentOfTotal}`}>
                    <path className="requests-analytics__dashboard-segment" d={item.path} stroke={item.color} />
                  </Tooltip>
                ))}
              </svg>
              <div className="requests-analytics__dashboard-label">
                <strong>{totalRequests}</strong>
                <span>{TEXT.total}</span>
              </div>
            </div>
            <StatusLegend items={visibleStatusSegments} dashboard />
          </div>
        ) : (
          <div className="requests-analytics__linear-summary">
            <div className="requests-analytics__summary-top">
              <span>{TEXT.total}</span>
              <strong>{totalRequests}</strong>
            </div>
            <div className="requests-analytics__stacked-bar" role="img" aria-label={TEXT.statusDistribution}>
              {visibleStatusSegments.map((item) => (
                <Tooltip key={item.key} title={`${item.label}: ${item.count} ${TEXT.total}, ${item.roundedPercent}% ${TEXT.percentOfTotal}`}>
                  <span
                    style={{
                      width: `${item.percent}%`,
                      minWidth: item.count > 0 ? 10 : 0,
                      backgroundColor: item.color,
                    }}
                  />
                </Tooltip>
              ))}
            </div>
            <StatusLegend items={visibleStatusSegments} />
          </div>
        )}
      </div>

      <div className="requests-analytics__grid">
        {analyticsStatuses.map((item) => {
          const percent = percentOfTotal(item.count);
          const isOpen = expandedStatusKeys.includes(item.key);

          return (
            <div className="requests-status-card" key={item.key} style={{ ["--status-color" as string]: item.color }}>
              <div className="requests-status-card__top">
                <span className="requests-status-card__label-dot">{item.label}</span>
                <div className="requests-status-card__actions">
                  <strong>{item.count}</strong>
                  <button
                    className={`requests-status-card__toggle${isOpen ? " is-open" : ""}`}
                    type="button"
                    onClick={() => onToggleStatusList(item.key)}
                    aria-label={`${isOpen ? TEXT.hideStudents : TEXT.showStudents}: ${item.label}`}
                  >
                    <DownOutlined />
                  </button>
                </div>
              </div>

              {chartView === "circle" ? (
                <Tooltip title={`${item.count} ${TEXT.total}, ${percent}% ${TEXT.percentOfTotal}`}>
                  <div className="requests-status-card__circle">
                    <Progress
                      type="circle"
                      percent={percent}
                      strokeColor={item.color}
                      trailColor="#edf2f7"
                      strokeWidth={10}
                      size={104}
                      format={() => (
                        <div className="requests-status-card__circle-label">
                          <strong>{percent}%</strong>
                        </div>
                      )}
                    />
                  </div>
                </Tooltip>
              ) : (
                <div className="requests-status-card__bar">
                  <Progress percent={percent} showInfo={false} strokeColor={item.color} trailColor="#eef2f7" strokeWidth={10} />
                </div>
              )}
              <small>
                {percent}% {TEXT.percentOfTotal}
              </small>

              {isOpen && (
                <div className="requests-status-card__students">
                  {item.students.length > 0 ? (
                    item.students.map((request) => (
                      <div className="requests-status-card__student" key={request.id}>
                        <span className="requests-status-card__student-name">{request.studentName || "-"}</span>
                        {item.showStatus && <span className="requests-status-card__student-status">{request.status || "-"}</span>}
                      </div>
                    ))
                  ) : (
                    <div className="requests-status-card__empty">{TEXT.noStudents}</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

type StatusLegendProps = {
  items: Array<AnalyticsStatus & { roundedPercent: number }>;
  dashboard?: boolean;
};

function StatusLegend({ items, dashboard = false }: StatusLegendProps) {
  return (
    <div className={`requests-analytics__line-labels${dashboard ? " requests-analytics__line-labels--dashboard" : ""}`}>
      {items.map((item) => (
        <span key={item.key} style={{ ["--status-color" as string]: item.color }}>
          {item.label}
          <strong>{item.roundedPercent}%</strong>
        </span>
      ))}
    </div>
  );
}

export function buildAnalyticsStatuses(
  statusCounts: Record<string, number>,
  displayedStatuses: string[],
  filteredRequests: AnalyticsStatus["students"]
): AnalyticsStatus[] {
  const displayedStatusSet = new Set(displayedStatuses);
  const otherStudents = filteredRequests.filter((request) => !displayedStatusSet.has(request.status || ""));

  return [
    ...ORGANIZER_REQUEST_STATUSES.filter((status) => displayedStatusSet.has(status)).map((status) => ({
      key: status,
      label: status,
      count: statusCounts[status] || 0,
      color: REQUEST_STATUS_COLORS[status] || OTHER_STATUS_COLOR,
      students: filteredRequests.filter((request) => request.status === status),
    })),
    {
      key: OTHER_STATUS_KEY,
      label: TEXT.other,
      count: otherStudents.length,
      color: OTHER_STATUS_COLOR,
      students: otherStudents,
      showStatus: true,
    },
  ];
}
