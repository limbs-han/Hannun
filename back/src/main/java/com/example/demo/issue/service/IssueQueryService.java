package com.example.demo.issue.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.service.ArticleQueryService;
import com.example.demo.common.pagination.CursorPage;
import com.example.demo.issue.domain.Issue;
import com.example.demo.issue.dto.IssueDetailResponse;
import com.example.demo.issue.dto.IssueDetailResponse.ArticlePreview;
import com.example.demo.issue.dto.IssueDetailResponse.StanceRatio;
import com.example.demo.issue.dto.IssueDetailResponse.ViewpointGroupPage;
import com.example.demo.issue.dto.IssueDetailResponse.ViewpointGroupSummary;
import com.example.demo.issue.dto.IssueFeedResponse;
import com.example.demo.issue.dto.IssueFeedResponse.IssueSummary;
import com.example.demo.issue.dto.SearchListResponse;
import com.example.demo.issue.dto.SearchListResponse.SearchItem;
import com.example.demo.issue.dto.SearchSuggestionsResponse;
import com.example.demo.issue.dto.ViewpointGroupArticlesResponse;
import com.example.demo.issue.exception.IssueNotFoundException;
import com.example.demo.issue.repository.IssueRepository;
import com.example.demo.issue.repository.IssueSearchRow;
import com.example.demo.issue.service.strategy.IssueFeedStrategy;
import com.example.demo.issue.service.strategy.IssueFeedStrategyResolver;
import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import com.example.demo.viewpointgroup.exception.ViewpointGroupNotFoundException;
import com.example.demo.viewpointgroup.repository.StanceSum;
import com.example.demo.viewpointgroup.service.ViewpointGroupQueryService;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;

@Service
@Transactional(readOnly = true)
@RequiredArgsConstructor
public class IssueQueryService {

    public static final String ISSUE_FEED_CACHE = "issueFeed";
    public static final String ISSUE_DETAIL_CACHE = "issueDetail";

    private final IssueRepository issueRepository;
    private final ArticleQueryService articleQueryService;
    private final ViewpointGroupQueryService viewpointGroupQueryService;
    private final IssueFeedStrategyResolver issueFeedStrategyResolver;
    private final StanceResolver stanceResolver;
    private final SearchEventPublisher searchEventPublisher;
    private final SearchPopularityAggregator searchPopularityAggregator;

    @Cacheable(cacheNames = ISSUE_FEED_CACHE,
            key = "#category + ':' + #sort + ':' + (#cursorValue ?: '0') + ':' + (#cursorId ?: '0')")
    public IssueFeedResponse getFeed(String category, String sort, String cursorValue, Long cursorId, int size) {
        String categoryFilter = "ALL".equals(category) ? null : category;
        IssueFeedStrategy strategy = issueFeedStrategyResolver.resolve(sort);
        List<Issue> rows = strategy.fetchRows(categoryFilter, cursorValue, cursorId, size);

        CursorPage<Issue> cursorPage = CursorPage.of(rows, size);
        List<IssueSummary> items = cursorPage.items().stream().map(this::toSummary).toList();

        if (!cursorPage.hasNext()) {
            return new IssueFeedResponse(items, null, null, false);
        }

        Issue last = cursorPage.last();
        return new IssueFeedResponse(items, strategy.extractCursorValue(last), last.getClusterId(), true);
    }

    // 날짜 범위 검색 전용 - 기존 getFeed의 IssueFeedStrategy(trending/latest)는 date range 인자가 없어서
    // 억지로 끼워맞추기보다 여기서 직접 분기. sort는 이 기간 안에서의 정렬 기준일 뿐(최신순 강제 아님).
    @Cacheable(cacheNames = ISSUE_FEED_CACHE,
            key = "'dateRange:' + #category + ':' + #sort + ':' + #from + ':' + #to + ':' + (#cursorValue ?: '0') + ':' + (#cursorId ?: '0')")
    public IssueFeedResponse getFeedByDateRange(String category, String sort, OffsetDateTime from, OffsetDateTime to,
                                                 String cursorValue, Long cursorId, int size) {
        String categoryFilter = "ALL".equals(category) ? null : category;
        boolean trending = "trending".equals(sort);

        List<Issue> rows;
        if (trending) {
            Long cursorScore = cursorValue == null ? null : Long.valueOf(cursorValue);
            rows = issueRepository.findByDateRangeTrending(from, to, categoryFilter, cursorScore, cursorId, size + 1);
        } else {
            OffsetDateTime cursorLastReportedAt = cursorValue == null ? null : OffsetDateTime.parse(cursorValue);
            rows = issueRepository.findByDateRangeLatest(from, to, categoryFilter, cursorLastReportedAt, cursorId, size + 1);
        }

        CursorPage<Issue> cursorPage = CursorPage.of(rows, size);
        List<IssueSummary> items = cursorPage.items().stream().map(this::toSummary).toList();

        if (!cursorPage.hasNext()) {
            return new IssueFeedResponse(items, null, null, false);
        }

        Issue last = cursorPage.last();
        Object nextCursorValue = trending ? last.getScore() : last.getLastReportedAt();
        return new IssueFeedResponse(items, nextCursorValue, last.getClusterId(), true);
    }

    @Cacheable(cacheNames = ISSUE_DETAIL_CACHE, key = "#issueId + ':' + #stance + ':' + #page")
    public IssueDetailResponse getDetail(Long issueId, String stance, int page, int size) {
        stanceResolver.validate(stance);

        Issue issue = issueRepository.findById(issueId)
                .orElseThrow(() -> new IssueNotFoundException(issueId));

        List<StanceSum> stanceSums = viewpointGroupQueryService.sumArticleCountByStance(issueId);
        StanceRatio stanceRatio = stanceResolver.calculateRatio(stanceSums);

        Pageable pageable = PageRequest.of(page, size);
        Page<ViewpointGroup> groupPage = viewpointGroupQueryService.findByClusterIdAndStance(issueId, stance, pageable);

        List<ViewpointGroupSummary> viewpointGroups = groupPage.getContent().stream()
                .map(this::toViewpointGroupSummary)
                .toList();

        ViewpointGroupPage viewpointGroupPage = new ViewpointGroupPage(
                groupPage.getNumber(), groupPage.getSize(), groupPage.getTotalElements(), groupPage.getTotalPages());

        return new IssueDetailResponse(issue.getClusterId(), issue.getCategory(),
                issue.getFirstReportedAt(), issue.getLastReportedAt(),
                issue.getPressCount(), issue.getArticleCount(), issue.getFactSummary(),
                emptyIfNull(issue.getCommonFactsBriefing()),
                stanceRatio, stance, viewpointGroups, viewpointGroupPage);
    }

    public SearchListResponse search(String keyword, String category, Double cursorValue, Long cursorId, int size) {
        List<IssueSearchRow> rows = issueRepository.searchByKeyword(keyword, category, cursorValue, cursorId, size + 1);
        CursorPage<IssueSearchRow> cursorPage = CursorPage.of(rows, size);
        List<SearchItem> items = cursorPage.items().stream().map(this::toSearchItem).toList();

        // cursor가 둘 다 없을 때만 = 실제 "검색 실행"(첫 페이지). 이후 스크롤(SEARCH_SCROLL)은 인기 검색어 집계 대상이 아님.
        if (cursorValue == null && cursorId == null) {
            searchEventPublisher.publishSearchExecuted(keyword);
        }

        if (!cursorPage.hasNext()) {
            return new SearchListResponse("LIST", keyword, items, null, null, false);
        }

        IssueSearchRow last = cursorPage.last();
        return new SearchListResponse("LIST", keyword, items, last.getRelevance(), last.getClusterId(), true);
    }

    public SearchSuggestionsResponse getSearchSuggestions(int size) {
        return new SearchSuggestionsResponse(searchPopularityAggregator.getPopularKeywords(size));
    }

    public ViewpointGroupArticlesResponse getViewpointGroupArticles(Long issueId, Long groupId,
                                                                      OffsetDateTime cursorPublished, Long cursorArticleId, int size) {
        ViewpointGroup group = viewpointGroupQueryService.getById(groupId);
        if (!group.getClusterId().equals(issueId)) {
            throw new ViewpointGroupNotFoundException(groupId);
        }

        List<Article> rows = articleQueryService.findByViewpointGroupIdWithCursor(
                groupId, cursorPublished, cursorArticleId, size + 1);
        CursorPage<Article> cursorPage = CursorPage.of(rows, size);
        List<ArticlePreview> items = cursorPage.items().stream().map(this::toArticlePreview).toList();

        if (!cursorPage.hasNext()) {
            return new ViewpointGroupArticlesResponse(items, null, null, false);
        }

        Article last = cursorPage.last();
        return new ViewpointGroupArticlesResponse(items, last.getPublished(), last.getId(), true);
    }

    private IssueSummary toSummary(Issue issue) {
        return new IssueSummary(issue.getClusterId(), issue.getCategory(), issue.getPressCount(),
                issue.getArticleCount(), issue.getScore(), issue.getFactSummary(),
                emptyIfNull(issue.getCommonFactsBriefing()));
    }

    // 아직 재클러스터링 안 된 옛날 이슈는 DB에 null로 남아있음 - 응답 JSON은 null 대신 빈 배열로 통일.
    private List<String> emptyIfNull(List<String> commonFactsBriefing) {
        return commonFactsBriefing == null ? List.of() : commonFactsBriefing;
    }

    private ViewpointGroupSummary toViewpointGroupSummary(ViewpointGroup group) {
        List<Article> previewArticles = articleQueryService.findTop3ByViewpointGroupId(group.getId());
        List<ArticlePreview> previews = previewArticles.stream().map(this::toArticlePreview).toList();
        int remainingCount = group.getArticleCount() - previews.size();

        return new ViewpointGroupSummary(group.getId(), group.getLabel(), group.getStance(),
                group.getArticleCount(), group.getPressCount(), previews, remainingCount);
    }

    private SearchItem toSearchItem(IssueSearchRow row) {
        return new SearchItem(row.getClusterId(), row.getCategory(), row.getFactSummary(),
                row.getArticleCount(), row.getPressCount());
    }

    private ArticlePreview toArticlePreview(Article article) {
        return new ArticlePreview(article.getId(), article.getCompany(), article.getTitle(), article.getLink(),
                article.getPublished(), article.getCategory(), article.getCategoryStr(), article.getReporter(),
                article.getThumbnailUrl());
    }
}
