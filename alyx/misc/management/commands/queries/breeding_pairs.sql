SELECT subjects_breedingpair.id,
subjects_breedingpair.name,
subjects_breedingpair.description,
subjects_breedingpair.start_date,
subjects_breedingpair.end_date,
f.nickname AS father_name,
m1.nickname AS mother1_name,
m2.nickname AS mother2_name,
subjects_line.name AS line,
subjects_breedingpair.json
FROM subjects_breedingpair
LEFT JOIN subjects_line on subjects_breedingpair.line_id=subjects_line.id
LEFT JOIN subjects_subject f on subjects_breedingpair.father_id=f.id
LEFT JOIN subjects_subject m1 on subjects_breedingpair.mother1_id=m1.id
LEFT JOIN subjects_subject m2 on subjects_breedingpair.mother2_id=m2.id
