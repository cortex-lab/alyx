SELECT subjects_subjectrequest.id,
subjects_subjectrequest.json,
subjects_subjectrequest.count,
subjects_subjectrequest.date_time,
subjects_subjectrequest.due_date,
subjects_subjectrequest.notes,
subjects_line.name AS line_name,
auth_user.username AS username
FROM subjects_subjectrequest
LEFT JOIN subjects_line on subjects_subjectrequest.line_id=subjects_line.id
LEFT JOIN auth_user on subjects_subjectrequest.user_id=auth_user.id
