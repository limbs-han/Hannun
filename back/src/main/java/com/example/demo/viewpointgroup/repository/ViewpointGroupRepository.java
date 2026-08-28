package com.example.demo.viewpointgroup.repository;

import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ViewpointGroupRepository extends JpaRepository<ViewpointGroup, Long> {
    Optional<ViewpointGroup> findByClusterIdAndLabel(Long clusterId, String label);

    Page<ViewpointGroup> findByClusterIdAndStanceOrderByArticleCountDesc(Long clusterId, String stance, Pageable pageable);

    @Query("select new com.example.demo.viewpointgroup.repository.StanceSum(v.stance, sum(v.articleCount)) " +
            "from ViewpointGroup v where v.clusterId = :clusterId group by v.stance")
    List<StanceSum> sumArticleCountByStance(@Param("clusterId") Long clusterId);
}
